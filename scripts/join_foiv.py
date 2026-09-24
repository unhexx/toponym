#!/usr/bin/env python3
"""Join Wikidata Q-ids onto existing FOIV rows (ukase-326).

Not a harvest: agencies-foiv.csv keeps foiv:{slug} ids. SPARQL P31 is
ministry Q4481741, federal service Q4481675, federal agency Q14944295
(P17=Q159); Q4481793/Q4481792 are out. 0/69 matches does not write.
SPARQL JSON/CSV is not vendored. Daily stays known_ids_only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import requests

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.csvio import PLACES_HEADER, write_csv  # noqa: E402
from scripts.lib.detectors import build_session  # noqa: E402
from scripts.lib.harvest import (  # noqa: E402
    HarvestCounts,
    SeedError,
    dump_csv_bytes_or_raise,
    incoming_for_upsert,
    load_rows_from_csv,
    load_rows_from_json,
    merge_bindings,
    p31_from_query,
    read_table,
    sparql_csv,
    utc_today,
)
from scripts.lib.harvest import load_main_query as load_main_query_required  # noqa: E402
from scripts.lib.invariants import yo_to_e  # noqa: E402
from scripts.lib.upsert import upsert_rows  # noqa: E402

ROOT = _ROOT
SPARQL_PATH = Path("data/raw/wikidata/foiv-ru.sparql")
FOIV_REL = Path("data/curated/agencies-foiv.csv")
ALLOWED_P31 = frozenset({"Q4481741", "Q4481675", "Q14944295"})
BLOCKED_P31 = frozenset({"Q4481793", "Q4481792"})
JOIN_FILL = ("wd", "name_en")
EXTRA_QID_SETS = ("p31",)
EXTRA_SCALARS = ("short", "dissolved")
FOIV_N = 69
__all__ = [
    "ALLOWED_P31",
    "apply_join",
    "join_foiv",
    "load_main_query",
    "main",
    "match_records",
    "norm_label",
    "p31_from_query",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Join Wikidata Q-id на ФОИВ (не harvest; 0/69 не пишет)"
    )
    parser.add_argument("--root", default=str(ROOT), help="корень репозитория")
    parser.add_argument(
        "--today",
        metavar="YYYY-MM-DD",
        help="updated_at (по умолчанию UTC сегодня)",
    )
    parser.add_argument(
        "--from-json",
        metavar="PATH",
        help="готовые строки SPARQL (тесты); без сети",
    )
    parser.add_argument(
        "--from-csv",
        metavar="PATH",
        help="кэш CSV того же SPARQL вне git; без основного запроса",
    )
    parser.add_argument("--dry-run", action="store_true", help="не писать CSV")
    return parser.parse_args(argv)


def load_main_query(path: Path) -> str:
    return load_main_query_required(
        path,
        required=("SELECT", "VALUES", "?type", "Q4481741", "Q4481675", "Q14944295"),
    )


def norm_label(value: str) -> str:
    text = yo_to_e((value or "").strip()).casefold()
    for token in ("«", "»", '"', "“", "”"):
        text = text.replace(token, "")
    return " ".join(text.split())


def _p31(rec: dict[str, Any]) -> set[str]:
    raw = rec.get("p31") or set()
    return {str(item) for item in raw}


def match_records(
    records: dict[str, dict[str, Any]],
    existing: list[dict[str, str]],
) -> dict[str, str]:
    """Map existing FOIV id → Wikidata Q-id. Unique name/abbr only.

    A second live Q-id for the same FOIV blacklists that id for the rest
    of the pass (the stale qid_to_foiv entry is dropped). Non-empty
    dissolved is skipped before the name match.
    """
    key_to_ids: dict[str, set[str]] = {}
    for row in existing:
        rid = (row.get("id") or "").strip()
        if not rid:
            continue
        for raw in (row.get("name_ru"), row.get("abbr")):
            key = norm_label(str(raw or ""))
            if key:
                key_to_ids.setdefault(key, set()).add(rid)
    foiv_to_qid: dict[str, str] = {}
    qid_to_foiv: dict[str, str] = {}
    blocked: set[str] = set()
    for qid, rec in records.items():
        if _p31(rec) & BLOCKED_P31:
            continue
        if not (_p31(rec) & ALLOWED_P31):
            continue
        if str(rec.get("dissolved") or "").strip():
            continue
        hits: set[str] = set()
        for raw in (rec.get("ru"), rec.get("short")):
            key = norm_label(str(raw or ""))
            if not key:
                continue
            ids = key_to_ids.get(key) or set()
            if len(ids) == 1:
                hits.update(ids)
        if len(hits) != 1:
            continue
        foiv_id = next(iter(hits))
        if foiv_id in blocked:
            continue
        if foiv_id in foiv_to_qid and foiv_to_qid[foiv_id] != qid:
            stale = foiv_to_qid.pop(foiv_id)
            if qid_to_foiv.get(stale) == foiv_id:
                qid_to_foiv.pop(stale, None)
            blocked.add(foiv_id)
            continue
        if qid in qid_to_foiv and qid_to_foiv[qid] != foiv_id:
            continue
        foiv_to_qid[foiv_id] = qid
        qid_to_foiv[qid] = foiv_id
    return foiv_to_qid


def apply_join(
    records: dict[str, dict[str, Any]],
    *,
    existing: list[dict[str, str]],
    today: str,
) -> tuple[list[dict[str, str]], HarvestCounts, int]:
    counts = HarvestCounts(incoming=len(records))
    matched = match_records(records, existing)
    by_id = {row.get("id", ""): row for row in existing if row.get("id")}
    incoming: list[dict[str, str]] = []
    for foiv_id, qid in matched.items():
        existing_row = by_id.get(foiv_id)
        if existing_row is None:
            continue
        rec = records[qid]
        mapped = {key: "" for key in PLACES_HEADER}
        mapped.update(
            {
                "id": foiv_id,
                "wd": qid,
                "name_en": str(rec.get("en") or ""),
                "updated_at": today,
            }
        )
        inc = incoming_for_upsert(mapped, existing_row, fill=JOIN_FILL)
        if inc is None:
            continue
        inc["updated_at"] = today
        incoming.append(inc)
    places, upsert_counts = upsert_rows(existing, incoming, header=PLACES_HEADER)
    counts.inserted = upsert_counts.inserted
    counts.updated = upsert_counts.updated
    counts.deprecated = upsert_counts.deprecated
    if counts.inserted != 0:
        raise SeedError("FOIV join не вставляет строки")
    if not matched:
        raise SeedError(f"FOIV join: 0/{FOIV_N} (не сливать)")
    return places, counts, len(matched)


def join_foiv(
    *,
    root: Path,
    today: str,
    from_json: Path | None,
    from_csv: Path | None,
    session: requests.Session | None = None,
) -> tuple[list[dict[str, str]], HarvestCounts, int, list[str]]:
    header, existing = read_table(root / FOIV_REL, PLACES_HEADER)
    if header and header != PLACES_HEADER:
        raise SeedError(f"agencies-foiv.csv: заголовок {header}")
    if from_json is not None:
        rows = load_rows_from_json(from_json)
    elif from_csv is not None:
        rows = load_rows_from_csv(from_csv)
    else:
        query = load_main_query(root / SPARQL_PATH)
        if session is None:
            session = build_session()
        print("sparql foiv Q4481741+Q4481675+Q14944295", file=sys.stderr)
        rows = sparql_csv(session, query, timeout=90)
        print(f"sparql rows={len(rows)}", file=sys.stderr)
        if not rows:
            raise SeedError("SPARQL: пусто")
    records = merge_bindings(
        rows, extra_scalars=EXTRA_SCALARS, extra_qid_sets=EXTRA_QID_SETS
    )
    places, counts, matched = apply_join(records, existing=existing, today=today)
    payload = dump_csv_bytes_or_raise(PLACES_HEADER, places, "agencies-foiv.csv")
    counts.bytes_places = len(payload)
    return places, counts, matched, PLACES_HEADER


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    today = args.today or utc_today()
    from_json = Path(args.from_json) if args.from_json else None
    from_csv = Path(args.from_csv) if args.from_csv else None
    try:
        places, counts, matched, header = join_foiv(
            root=root,
            today=today,
            from_json=from_json,
            from_csv=from_csv,
        )
        if not args.dry_run:
            write_csv(root / FOIV_REL, header, places)
    except SeedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    prefix = "dry-run" if args.dry_run else "ok"
    print(
        f"{prefix}\tmatched={matched}/{FOIV_N}\tincoming={counts.incoming}"
        f"\tinserted={counts.inserted}\tupdated={counts.updated}"
        f"\tbytes_places={counts.bytes_places}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
