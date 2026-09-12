#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.catalog import (  # noqa: E402
    load_catalog,
    patch_catalog_source,
    stamp_catalog_updated,
)
from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv  # noqa: E402
from scripts.lib.detectors import (  # noqa: E402
    _request,
    build_session,
    expand_url,
    utcnow,
    yesterday_utc,
)
from scripts.lib.places import PLACE_RELPATHS  # noqa: E402
from scripts.lib.upsert import (  # noqa: E402
    DEFAULT_MAX_VENDOR_BYTES,
    UpsertCounts,
    apply_geonames,
    too_large,
    upsert_rows,
)

ROOT = _ROOT
CATALOG_PATH = ROOT / "data" / "sources" / "catalog.yaml"


class SyncError(Exception):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upsert канона toponym")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--source", metavar="ID", help="один источник из каталога")
    group.add_argument("--all", action="store_true", help="все источники (по умолчанию)")
    parser.add_argument("--apply", action="store_true", help="записать изменения")
    parser.add_argument("--dry-run", action="store_true", help="только отчёт (по умолчанию)")
    parser.add_argument("--manual-file", metavar="PATH", help="канонический CSV для ukase-326")
    parser.add_argument(
        "--check-json",
        default="",
        help="отчёт check.py: cursor_new для источников changed без error",
    )
    return parser.parse_args(argv)


def cursors_from_check_report(report: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(report, dict):
        return out
    for row in report.get("sources") or []:
        if not isinstance(row, dict) or row.get("error") or not row.get("changed"):
            continue
        source_id = row.get("id")
        cursor_new = row.get("cursor_new") or ""
        if source_id and cursor_new:
            out[str(source_id)] = str(cursor_new)
    return out


def load_check_cursors(path: Path | str | None) -> dict[str, str]:
    if path is None:
        return {}
    path = Path(path)
    if not path.is_file():
        raise SyncError(f"нет файла {path}")
    return cursors_from_check_report(json.loads(path.read_text(encoding="utf-8")))


def _header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    getter = getattr(headers, "get", None)
    if getter is None:
        return ""
    value = getter(name) or getter(name.lower()) or ""
    return str(value).strip()


def _refuse_vendor_dump(source: dict[str, Any], session: requests.Session | None) -> None:
    url = source.get("url") or ""
    max_bytes = int(source.get("max_vendor_bytes") or DEFAULT_MAX_VENDOR_BYTES)
    if not source.get("vendor"):
        return
    if not url or session is None:
        return
    response = _request(session, "HEAD", url)
    if response.status_code >= 400:
        response = _request(session, "GET", url, stream=True)
        length = _header(response.headers, "Content-Length")
        if getattr(response, "raw", None) is not None:
            response.close()
    else:
        length = _header(response.headers, "Content-Length")
    if too_large(length, max_bytes):
        raise SyncError(
            f"{source.get('id')}: Content-Length {length} > max_vendor_bytes {max_bytes}"
        )


def _fetch_text(session: requests.Session, url: str) -> str:
    response = _request(session, "GET", url)
    if response.status_code == 404:
        return ""
    if response.status_code >= 400:
        raise SyncError(f"HTTP {response.status_code} {url}")
    return response.text or ""


def sync_geonames(
    source: dict[str, Any],
    *,
    root: Path,
    apply: bool,
    session: requests.Session,
    today: str,
    now: datetime,
) -> UpsertCounts:
    if source.get("vendor"):
        _refuse_vendor_dump(source, session)
    detector = source.get("detector") or {}
    urls = [expand_url(url, now=now) for url in detector.get("urls") or []]
    if len(urls) < 1:
        urls = [
            expand_url(
                "https://download.geonames.org/export/dump/modifications-{yesterday}.txt",
                now=now,
            ),
            expand_url(
                "https://download.geonames.org/export/dump/deletes-{yesterday}.txt",
                now=now,
            ),
        ]
    mods_body = _fetch_text(session, urls[0])
    deletes_body = _fetch_text(session, urls[1]) if len(urls) > 1 else ""

    total = UpsertCounts()
    for rel in PLACE_RELPATHS:
        path = root / rel
        if not path.is_file():
            continue
        header, rows = read_csv(path)
        new_rows, counts = apply_geonames(rows, mods_body, deletes_body, today=today)
        total.add(counts)
        if apply:
            write_csv(path, header, new_rows)
    if apply:
        patch_catalog_source(
            root / "data" / "sources" / "catalog.yaml",
            source["id"],
            checked_at=today,
            cursor=yesterday_utc(now),
        )
    return total


def sync_ukase(
    source: dict[str, Any],
    *,
    root: Path,
    apply: bool,
    manual_file: Path | None,
    today: str,
    cursor: str | None = None,
) -> UpsertCounts:
    counts = UpsertCounts()
    if manual_file is not None:
        header, incoming = read_csv(manual_file)
        if header != PLACES_HEADER:
            raise SyncError("manual-file: нужен канонический 22-колоночный заголовок")
        target = root / "data" / "curated" / "agencies-foiv.csv"
        if not target.is_file():
            raise SyncError(f"нет файла {target}")
        existing_header, existing = read_csv(target)
        new_rows, counts = upsert_rows(existing, incoming, header=existing_header)
        if apply:
            write_csv(target, existing_header, new_rows)
    if apply:
        patch_catalog_source(
            root / "data" / "sources" / "catalog.yaml",
            source["id"],
            checked_at=today,
            cursor=cursor,
        )
    return counts


def sync_pointer(
    source: dict[str, Any],
    *,
    root: Path,
    apply: bool,
    today: str,
    cursor: str | None = None,
) -> UpsertCounts:
    if apply:
        kwargs: dict[str, str] = {"checked_at": today}
        if cursor is not None:
            kwargs["cursor"] = cursor
        patch_catalog_source(
            root / "data" / "sources" / "catalog.yaml",
            source["id"],
            **kwargs,
        )
    return UpsertCounts()


def sync_source(
    source: dict[str, Any],
    *,
    root: Path,
    apply: bool,
    manual_file: Path | None,
    session: requests.Session | None,
    now: datetime,
    cursor: str | None = None,
) -> UpsertCounts:
    today = now.date().isoformat()
    source_id = source["id"]

    if source.get("vendor"):
        if session is None:
            raise SyncError(f"{source_id}: нет HTTP-сессии для vendor")
        _refuse_vendor_dump(source, session)

    if source_id == "geonames-ru":
        if session is None:
            raise SyncError("geonames-ru: нет HTTP-сессии")
        return sync_geonames(
            source, root=root, apply=apply, session=session, today=today, now=now
        )
    if source_id == "ukase-326":
        return sync_ukase(
            source,
            root=root,
            apply=apply,
            manual_file=manual_file,
            today=today,
            cursor=cursor,
        )
    return sync_pointer(source, root=root, apply=apply, today=today, cursor=cursor)


def run_sync(
    *,
    source_id: str | None,
    apply: bool,
    manual_file: Path | None,
    session: requests.Session | None,
    now: datetime | None = None,
    root: Path | None = None,
    catalog_path: Path | None = None,
    check_json: Path | str | None = None,
) -> tuple[dict[str, Any], int]:
    root = root or ROOT
    catalog_path = catalog_path or (root / "data" / "sources" / "catalog.yaml")
    current = now or utcnow()
    catalog = load_catalog(catalog_path)
    cursors = load_check_cursors(check_json)
    if source_id:
        sources = [row for row in catalog.get("sources", []) if row.get("id") == source_id]
        if not sources:
            raise SyncError(f"неизвестный источник {source_id}")
    else:
        sources = list(catalog.get("sources", []))

    total = UpsertCounts()
    per_source: list[dict[str, Any]] = []
    for source in sources:
        counts = sync_source(
            source,
            root=root,
            apply=apply,
            manual_file=manual_file if source.get("id") == "ukase-326" else None,
            session=session,
            now=current,
            cursor=cursors.get(str(source["id"])),
        )
        total.add(counts)
        per_source.append({"id": source["id"], **counts.as_dict()})

    if apply:
        stamp_catalog_updated(catalog_path, current.date().isoformat())

    report = {
        "as_of": current.strftime("%Y-%m-%dT%H:%M:%SZ")
        if current.tzinfo
        else f"{current.isoformat()}Z",
        "apply": apply,
        **total.as_dict(),
        "sources": per_source,
    }
    return report, 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    apply = bool(args.apply) and not bool(args.dry_run)
    manual = Path(args.manual_file) if args.manual_file else None
    if manual is not None and not manual.is_file():
        print(f"нет файла {manual}", file=sys.stderr)
        return 2
    try:
        session = build_session()
        report, code = run_sync(
            source_id=args.source,
            apply=apply,
            manual_file=manual,
            session=session,
            now=utcnow(),
            root=ROOT,
            catalog_path=CATALOG_PATH,
            check_json=Path(args.check_json) if args.check_json else None,
        )
    except (SyncError, OSError, KeyError, ValueError, requests.RequestException) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
