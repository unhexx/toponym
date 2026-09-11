#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.catalog import get_source, load_catalog  # noqa: E402
from scripts.lib.detectors import _request, build_session  # noqa: E402

ROOT = _ROOT

# Каталог даёт прямой архив. Остальные — порталы: нужен --url.
DIRECT_DUMPS = {
    "geonames-ru": "RU.zip",
}
POINTER_DUMPS = {
    "fias-gar": "gar.zip",
    "gkgn-opendata": "gkgn.zip",
}
DUMP_IDS = frozenset(DIRECT_DUMPS) | frozenset(POINTER_DUMPS)


class FetchError(Exception):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Скачать дамп источника вне дерева git (не вендорить в data/)"
    )
    parser.add_argument("--source", metavar="ID", required=True, help="id из catalog.yaml")
    parser.add_argument(
        "--dest",
        metavar="DIR",
        help="каталог вне репозитория (по умолчанию $TOPONYM_DUMP_DIR или mkdtemp)",
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        help="прямой URL архива; обязателен для указателей ГАР/ГКГН",
    )
    parser.add_argument("--dry-run", action="store_true", help="печать URL и dest, без записи")
    parser.add_argument(
        "--root",
        metavar="PATH",
        default=str(ROOT),
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def is_inside_repo(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def assert_dest_outside_repo(dest: Path, root: Path) -> Path:
    resolved = dest.expanduser()
    if is_inside_repo(resolved, root):
        raise FetchError(
            f"dest внутри репозитория запрещён: {resolved} (корень {root.resolve()})"
        )
    parent = resolved.parent if resolved.exists() and resolved.is_file() else resolved
    if is_inside_repo(parent, root):
        raise FetchError(f"dest внутри репозитория запрещён: {resolved}")
    return resolved


def default_dest_dir() -> Path:
    env = (os.environ.get("TOPONYM_DUMP_DIR") or "").strip()
    if env:
        return Path(env).expanduser()
    return Path(tempfile.mkdtemp(prefix="toponym-dump-"))


def filename_from_url(url: str, fallback: str) -> str:
    name = Path(urlparse(url).path).name
    if name and name not in {".", "/"}:
        return name
    return fallback


def resolve_dump(
    source: dict[str, Any],
    *,
    url_override: str | None,
) -> tuple[str, str]:
    source_id = str(source.get("id") or "")
    if source_id not in DUMP_IDS:
        raise FetchError(
            f"{source_id}: не дамп RU.zip/ГАР/ГКГН; смотри data/raw/{source_id}/SOURCE.md"
        )
    if source_id in DIRECT_DUMPS:
        url = (url_override or source.get("url") or "").strip()
        if not url:
            raise FetchError(f"{source_id}: нет URL в каталоге")
        return url, filename_from_url(url, DIRECT_DUMPS[source_id])
    url = (url_override or "").strip()
    if not url:
        raise FetchError(
            f"{source_id}: каталог — указатель, не архив; передайте --url "
            f"(см. data/raw/{source_id}/SOURCE.md)"
        )
    return url, filename_from_url(url, POINTER_DUMPS[source_id])


def _write_body(response: Any, dest_file: Path) -> int:
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with dest_file.open("wb") as fh:
        iterator = getattr(response, "iter_content", None)
        if callable(iterator):
            for chunk in iterator(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                written += len(chunk)
            return written
        data = getattr(response, "content", b"") or b""
        fh.write(data)
        return len(data)


def download(session: Any, url: str, dest_file: Path) -> int:
    response = _request(session, "GET", url, stream=True)
    status = getattr(response, "status_code", 0)
    if status >= 400:
        closer = getattr(response, "close", None)
        if callable(closer):
            closer()
        raise FetchError(f"HTTP {status} {url}")
    try:
        return _write_body(response, dest_file)
    finally:
        closer = getattr(response, "close", None)
        if callable(closer):
            closer()


def fetch_dump(
    *,
    source_id: str,
    dest: Path | None,
    url: str | None,
    dry_run: bool,
    root: Path,
    catalog: dict[str, Any] | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    if catalog is None:
        catalog = load_catalog(root / "data" / "sources" / "catalog.yaml")
    try:
        source = get_source(catalog, source_id)
    except KeyError as exc:
        raise FetchError(f"нет источника {source_id} в каталоге") from exc
    dump_url, filename = resolve_dump(source, url_override=url)
    dest_dir = assert_dest_outside_repo(dest if dest is not None else default_dest_dir(), root)
    dest_file = dest_dir / filename
    if is_inside_repo(dest_file, root):
        raise FetchError(f"dest внутри репозитория запрещён: {dest_file}")
    result = {
        "id": source_id,
        "url": dump_url,
        "dest": str(dest_file),
        "bytes": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    if session is None:
        session = build_session()
    dest_dir.mkdir(parents=True, exist_ok=True)
    result["bytes"] = download(session, dump_url, dest_file)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    dest = Path(args.dest) if args.dest else None
    try:
        result = fetch_dump(
            source_id=args.source,
            dest=dest,
            url=args.url,
            dry_run=args.dry_run,
            root=root,
        )
    except FetchError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    prefix = "dry-run" if result["dry_run"] else "ok"
    print(f"{prefix}\t{result['id']}\t{result['url']}\t{result['dest']}\t{result['bytes']}")
    if not result["dry_run"]:
        print("не коммитить этот файл; в git только data/raw/*/SOURCE.md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
