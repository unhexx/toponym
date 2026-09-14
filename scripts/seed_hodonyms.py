#!/usr/bin/env python3
"""Harvest Russian streets from Wikidata SPARQL into data/curated/hodonyms.csv.

Coverage is Wikidata P31 in {Q79007, Q54114, Q628179, Q1251403, Q537127}, P17=Q159,
not FIAS/GAR. SPARQL JSON/CSV is not vendored; optional --from-csv/--from-json
is a cache outside git. Daily sync stays known_ids_only (wikidata.yaml).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import requests

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.csvio import PLACES_HEADER, write_csv  # noqa: E402
from scripts.lib.declensions import DECLENSIONS_HEADER  # noqa: E402
from scripts.lib.detectors import build_session  # noqa: E402
from scripts.lib.harvest import (  # noqa: E402
    HarvestCounts,
    ParentIndex,
    SeedError,
    declension_stub,
    dump_csv_bytes_or_raise,
    format_coord,
    hop_unresolved,
    incoming_for_upsert,
    load_rows_from_csv,
    load_rows_from_json,
    merge_bindings,
    p31_from_query,
    qid_from_uri,
    read_table,
    resolve_parent,
    sparql_csv,
    utc_today,
)
from scripts.lib.harvest import load_main_query as load_main_query_required  # noqa: E402
from scripts.lib.harvest import load_parent_index as load_parent_index_specs  # noqa: E402
from scripts.lib.harvest import queries_for_p31 as queries_for_p31_last  # noqa: E402
from scripts.lib.harvest import skip_ids as skip_ids_rels  # noqa: E402
from scripts.lib.invariants import yo_to_e  # noqa: E402
from scripts.lib.upsert import upsert_rows  # noqa: E402

ROOT = _ROOT
SPARQL_PATH = Path("data/raw/wikidata/hodonyms-ru.sparql")
HODONYMS_REL = Path("data/curated/hodonyms.csv")
DECL_REL = Path("data/declensions/hodonyms.csv")
CITIES_REL = Path("data/curated/cities-major.csv")
REGIONS_REL = Path("data/curated/regions.csv")
MUN_REL = Path("data/curated/municipalities.csv")
AGORONYMS_REL = Path("data/curated/agoronyms.csv")
DROMONYMS_REL = Path("data/curated/dromonyms.csv")
HODONYM_SPECS: tuple[tuple[Path, int], ...] = (
    (CITIES_REL, 0),
    (MUN_REL, 1),
    (REGIONS_REL, 2),
)
HODONYM_SKIP_RELS = (AGORONYMS_REL, DROMONYMS_REL)
HOP_BATCH = 80
__all__ = [
    "apply_harvest",
    "format_coord",
    "harvest",
    "is_square_name",
    "load_main_query",
    "load_parent_index",
    "load_rows_from_json",
    "main",
    "map_hodonym",
    "merge_bindings",
    "p31_from_query",
    "qid_from_uri",
    "queries_for_p31",
    "resolve_parent",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сиды годонимов из Wikidata SPARQL (не ГАР; не полный ФИАС)"
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
    parser.add_argument("--no-hop", action="store_true", help="не добирать parent через P131*")
    parser.add_argument("--dry-run", action="store_true", help="не писать CSV")
    parser.add_argument(
        "--hop-batch",
        type=int,
        default=HOP_BATCH,
        help="размер VALUES для P131* (по умолчанию 80)",
    )
    return parser.parse_args(argv)


def is_square_name(name: str) -> bool:
    return "площадь" in (name or "").casefold()


def load_main_query(path: Path) -> str:
    return load_main_query_required(path, required=("SELECT", "VALUES", "?type", "Q79007"))


def queries_for_p31(query: str) -> list[tuple[str, str]]:
    return queries_for_p31_last(query, last=("Q79007",))


def load_parent_index(root: Path) -> ParentIndex:
    return load_parent_index_specs(root, HODONYM_SPECS)


def skip_ids(root: Path) -> set[str]:
    return set(skip_ids_rels(root, HODONYM_SKIP_RELS))


def map_hodonym(
    rec: dict[str, Any],
    parent: tuple[str, str],
    today: str,
) -> dict[str, str]:
    ru_raw = str(rec.get("ru") or "").strip()
    name_ru = yo_to_e(ru_raw)
    name_yo = ru_raw if ru_raw != name_ru else ""
    qid = str(rec["qid"])
    row = {key: "" for key in PLACES_HEADER}
    row.update(
        {
            "id": f"wd:{qid}",
            "id_scheme": "wikidata",
            "type_id": "hodonym",
            "name_ru": name_ru,
            "name_yo": name_yo,
            "name_en": str(rec.get("en") or ""),
            "parent_id": parent[0],
            "admin1": parent[1],
            "lat": str(rec.get("lat") or ""),
            "lon": str(rec.get("lon") or ""),
            "wd": qid,
            "geonames": str(rec.get("gn") or ""),
            "status": "active",
            "source_id": "wikidata",
            "updated_at": today,
        }
    )
    return row


def apply_harvest(
    records: dict[str, dict[str, Any]],
    *,
    index: ParentIndex,
    existing_places: list[dict[str, str]],
    existing_decls: list[dict[str, str]],
    today: str,
    other_ids: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], HarvestCounts]:
    counts = HarvestCounts(incoming=len(records))
    by_id = {row.get("id", ""): row for row in existing_places if row.get("id")}
    incoming: list[dict[str, str]] = []
    new_places: list[dict[str, str]] = []
    for qid, rec in records.items():
        ru = str(rec.get("ru") or "").strip()
        if not ru:
            counts.skipped_other += 1
            continue
        if is_square_name(ru) or qid in other_ids:
            counts.skipped_square += 1
            continue
        parent = resolve_parent(index, rec["located"], rec["iso"])
        if parent is None:
            counts.skipped_parent += 1
            continue
        mapped = map_hodonym(rec, parent, today)
        rid = mapped["id"]
        if rid.startswith("gn:"):
            counts.skipped_other += 1
            continue
        inc = incoming_for_upsert(mapped, by_id.get(rid))
        if inc is None:
            continue
        incoming.append(inc)
        if rid not in by_id:
            new_places.append(mapped)
    places, upsert_counts = upsert_rows(existing_places, incoming, header=PLACES_HEADER)
    counts.inserted = upsert_counts.inserted
    counts.updated = upsert_counts.updated
    decl_seen = {(row.get("id"), row.get("lemma")) for row in existing_decls}
    decls = [dict(row) for row in existing_decls]
    for place in new_places:
        stub = declension_stub(place)
        key = (stub["id"], stub["lemma"])
        if key in decl_seen:
            continue
        decls.append(stub)
        decl_seen.add(key)
        counts.decl_added += 1
    return places, decls, counts


def harvest(
    *,
    root: Path,
    today: str,
    from_json: Path | None,
    from_csv: Path | None,
    hop: bool,
    hop_batch: int,
    session: requests.Session | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]], HarvestCounts, list[str], list[str]]:
    place_header, existing_places = read_table(root / HODONYMS_REL, PLACES_HEADER)
    decl_header, existing_decls = read_table(root / DECL_REL, DECLENSIONS_HEADER)
    if place_header and place_header != PLACES_HEADER:
        raise SeedError(f"hodonyms.csv: заголовок {place_header}")
    if decl_header and decl_header != DECLENSIONS_HEADER:
        raise SeedError(f"declensions/hodonyms.csv: заголовок {decl_header}")
    index = load_parent_index(root)
    if from_json is not None:
        rows = load_rows_from_json(from_json)
    elif from_csv is not None:
        rows = load_rows_from_csv(from_csv)
    else:
        query = load_main_query(root / SPARQL_PATH)
        if session is None:
            session = build_session()
        rows = []
        errors: list[str] = []
        for p31, typed in queries_for_p31(query):
            print(f"sparql P31={p31}", file=sys.stderr)
            try:
                chunk = sparql_csv(session, typed, timeout=90)
            except SeedError as exc:
                errors.append(f"{p31}: {exc}")
                print(f"sparql P31={p31} fail {exc}", file=sys.stderr)
                continue
            print(f"sparql P31={p31} rows={len(chunk)}", file=sys.stderr)
            rows.extend(chunk)
            time.sleep(0.4)
        if not rows:
            raise SeedError("SPARQL: " + "; ".join(errors) if errors else "пусто")
        if errors:
            print("sparql partial: " + "; ".join(errors), file=sys.stderr)
    records = merge_bindings(rows)
    counts = HarvestCounts()
    if hop and from_json is None:
        if session is None:
            session = build_session()
        counts.hopped = hop_unresolved(session, records, index, hop_batch)
    places, decls, applied = apply_harvest(
        records,
        index=index,
        existing_places=existing_places,
        existing_decls=existing_decls,
        today=today,
        other_ids=skip_ids(root),
    )
    applied.hopped = counts.hopped
    dump_csv_bytes_or_raise(PLACES_HEADER, places, "hodonyms.csv")
    return places, decls, applied, PLACES_HEADER, DECLENSIONS_HEADER


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    today = args.today or utc_today()
    from_json = Path(args.from_json) if args.from_json else None
    from_csv = Path(args.from_csv) if args.from_csv else None
    try:
        places, decls, counts, place_header, decl_header = harvest(
            root=root,
            today=today,
            from_json=from_json,
            from_csv=from_csv,
            hop=not args.no_hop,
            hop_batch=args.hop_batch,
        )
        if not args.dry_run:
            write_csv(root / HODONYMS_REL, place_header, places)
            write_csv(root / DECL_REL, decl_header, decls)
    except SeedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    prefix = "dry-run" if args.dry_run else "ok"
    print(
        f"{prefix}\tincoming={counts.incoming}\tinserted={counts.inserted}"
        f"\tupdated={counts.updated}\tskipped_parent={counts.skipped_parent}"
        f"\tskipped_square={counts.skipped_square}\thopped={counts.hopped}"
        f"\tdecl_added={counts.decl_added}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
