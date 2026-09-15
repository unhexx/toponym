#!/usr/bin/env python3
"""Harvest Russian cities from Wikidata into cities-major.csv.

Coverage is Wikidata P31=Q7930989 (city/town in Russia), P17=Q159, not the
official 1126-city list and not OKTMO. SPARQL JSON/CSV is not vendored;
optional --from-csv/--from-json is a cache outside git. Daily sync stays
known_ids_only (wikidata.yaml). Crimea / new subjects are skipped in the CLI.
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
    ALIAS_FILL,
    FILL_IF_EMPTY,
    HarvestCounts,
    ParentIndex,
    SeedError,
    declension_stub,
    dump_csv_bytes_or_raise,
    hop_unresolved,
    incoming_deprecate,
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
SPARQL_PATH = Path("data/raw/wikidata/cities-ru.sparql")
CITIES_REL = Path("data/curated/cities-major.csv")
DECL_REL = Path("data/declensions/cities-major.csv")
REGIONS_REL = Path("data/curated/regions.csv")
CITY_SPECS: tuple[tuple[Path, int], ...] = ((REGIONS_REL, 0),)
CITY_SKIP_RELS = (
    Path("data/curated/federal-districts.csv"),
    Path("data/curated/regions.csv"),
    Path("data/curated/hydronyms-major.csv"),
    Path("data/curated/oronyms-major.csv"),
    Path("data/curated/hodonyms.csv"),
    Path("data/curated/microtoponyms.csv"),
    Path("data/curated/dromonyms.csv"),
    Path("data/curated/villages.csv"),
    Path("data/curated/agoronyms.csv"),
    Path("data/curated/municipalities.csv"),
    Path("data/curated/agencies-foiv.csv"),
    Path("data/curated/agencies-other.csv"),
)
LOCAL_SUBJECT_IDS = (
    "local:ru-crimea",
    "local:ru-sevastopol",
    "local:ru-dnr",
    "local:ru-lnr",
    "local:ru-zaporozhye",
    "local:ru-kherson",
)
EXTRA_SCALARS = ("oktmo", "dissolved")
EXTRA_QID_SETS = ("replaced", "p31")
HOP_BATCH = 80
__all__ = [
    "CITY_SKIP_RELS",
    "CITY_SPECS",
    "LOCAL_SUBJECT_IDS",
    "apply_harvest",
    "harvest",
    "load_main_query",
    "load_parent_index",
    "main",
    "map_city",
    "oktmo_digits",
    "p31_from_query",
    "queries_for_p31",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сиды городов из Wikidata SPARQL (P31=Q7930989, не Росстат)"
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


def load_main_query(path: Path) -> str:
    return load_main_query_required(
        path, required=("SELECT", "VALUES", "?type", "Q7930989")
    )


def queries_for_p31(query: str) -> list[tuple[str, str]]:
    return queries_for_p31_last(query, last=())


def load_parent_index(root: Path) -> ParentIndex:
    return load_parent_index_specs(root, CITY_SPECS)


def skip_ids(root: Path) -> dict[str, str]:
    return skip_ids_rels(root, CITY_SKIP_RELS)


def oktmo_digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def map_city(
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
            "type_id": "city",
            "name_ru": name_ru,
            "name_yo": name_yo,
            "name_en": str(rec.get("en") or ""),
            "parent_id": parent[0],
            "admin1": parent[1],
            "lat": str(rec.get("lat") or ""),
            "lon": str(rec.get("lon") or ""),
            "wd": qid,
            "geonames": str(rec.get("gn") or ""),
            "oktmo": oktmo_digits(str(rec.get("oktmo") or "")),
            "status": "active",
            "source_id": "wikidata",
            "updated_at": today,
        }
    )
    return row


def _p31(rec: dict[str, Any]) -> set[str]:
    raw = rec.get("p31") or set()
    return {str(item) for item in raw}


def _prefer_replaced_by(
    replaced: set[str], known_ids: set[str], city_ids: set[str]
) -> str:
    hits: list[str] = []
    for raw in replaced:
        qid = qid_from_uri(str(raw)) or str(raw).strip()
        if qid.startswith("wd:"):
            ident = qid
        elif qid.startswith("Q"):
            ident = f"wd:{qid}"
        else:
            continue
        if ident in known_ids or ident in city_ids:
            hits.append(ident)
    if not hits:
        return ""
    preferred = [ident for ident in hits if ident in city_ids]
    return preferred[0] if preferred else hits[0]


def _lookup_existing(
    qid: str,
    by_id: dict[str, dict[str, str]],
    by_wd: dict[str, dict[str, str]],
) -> tuple[str, dict[str, str] | None]:
    via_id = by_id.get(f"wd:{qid}")
    via_wd = by_wd.get(qid)
    if via_id is not None and via_wd is not None and via_id.get("id") != via_wd.get("id"):
        return "overlap", None
    return "ok", via_id or via_wd


def apply_harvest(
    records: dict[str, dict[str, Any]],
    *,
    index: ParentIndex,
    existing_places: list[dict[str, str]],
    existing_decls: list[dict[str, str]],
    today: str,
    skip_map: dict[str, str],
    known_ids: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], HarvestCounts]:
    counts = HarvestCounts(incoming=len(records))
    original_ids = {row.get("id") for row in existing_places if row.get("id")}
    by_id = {row.get("id", ""): row for row in existing_places if row.get("id")}
    by_wd: dict[str, dict[str, str]] = {}
    for row in existing_places:
        wd = (row.get("wd") or "").strip()
        if wd.startswith("Q"):
            by_wd.setdefault(wd, row)
    city_ids = set(original_ids)
    incoming: list[dict[str, str]] = []
    new_places: list[dict[str, str]] = []

    for qid, rec in records.items():
        ru = str(rec.get("ru") or "").strip()
        if not ru:
            counts.skipped_other += 1
            continue
        if qid in skip_map:
            counts.skipped_overlap += 1
            print(f"skip overlap wd:{qid} table={skip_map[qid]}", file=sys.stderr)
            continue
        status, existing = _lookup_existing(qid, by_id, by_wd)
        if status == "overlap":
            counts.skipped_overlap += 1
            print(f"skip overlap wd:{qid} table=cities-major", file=sys.stderr)
            continue
        dissolved = bool(str(rec.get("dissolved") or "").strip())
        if dissolved and existing is None:
            counts.skipped_other += 1
            continue
        if dissolved and existing is not None:
            replaced = _prefer_replaced_by(
                {str(item) for item in (rec.get("replaced") or set())},
                known_ids,
                city_ids,
            )
            incoming.append(incoming_deprecate(existing["id"], replaced, today))
            continue
        parent = resolve_parent(
            index, rec.get("located") or set(), rec.get("iso") or set()
        )
        if parent is None:
            counts.skipped_parent += 1
            continue
        if parent[0] in LOCAL_SUBJECT_IDS:
            counts.skipped_other += 1
            continue
        mapped = map_city(rec, parent, today)
        if mapped["id"].startswith("gn:"):
            counts.skipped_other += 1
            continue
        if existing is not None:
            mapped["id"] = existing["id"]
            fill = ALIAS_FILL if existing["id"].startswith("local:") else FILL_IF_EMPTY
            inc = incoming_for_upsert(mapped, existing, fill=fill)
            if inc is not None:
                incoming.append(inc)
            continue
        inc = incoming_for_upsert(mapped, None, fill=FILL_IF_EMPTY)
        if inc is None:
            continue
        incoming.append(inc)
        new_places.append(mapped)
        rid = mapped["id"]
        by_id[rid] = mapped
        by_wd.setdefault(qid, mapped)
        city_ids.add(rid)

    places, upsert_counts = upsert_rows(existing_places, incoming, header=PLACES_HEADER)
    counts.inserted = upsert_counts.inserted
    counts.updated = upsert_counts.updated
    counts.deprecated = upsert_counts.deprecated
    decl_seen = {(row.get("id"), row.get("lemma")) for row in existing_decls}
    decls = [dict(row) for row in existing_decls]
    for place in new_places:
        if place["id"] in original_ids:
            continue
        stub = declension_stub(place, type_code="city")
        key = (stub["id"], stub["lemma"])
        if key in decl_seen:
            continue
        decls.append(stub)
        decl_seen.add(key)
        counts.decl_added += 1
    return places, decls, counts


def _merge_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    return merge_bindings(rows, extra_scalars=EXTRA_SCALARS, extra_qid_sets=EXTRA_QID_SETS)


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
    place_header, existing_places = read_table(root / CITIES_REL, PLACES_HEADER)
    decl_header, existing_decls = read_table(root / DECL_REL, DECLENSIONS_HEADER)
    if place_header and place_header != PLACES_HEADER:
        raise SeedError(f"cities-major.csv: заголовок {place_header}")
    if decl_header and decl_header != DECLENSIONS_HEADER:
        raise SeedError(f"declensions/cities-major.csv: заголовок {decl_header}")
    index = load_parent_index(root)
    skip_map = skip_ids(root)
    if from_json is not None:
        rows = load_rows_from_json(from_json)
        records = _merge_rows(rows)
    elif from_csv is not None:
        rows = load_rows_from_csv(from_csv)
        records = _merge_rows(rows)
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
            for row in chunk:
                if not row.get("type") and not row.get("p31"):
                    row["type"] = f"http://www.wikidata.org/entity/{p31}"
            rows.extend(chunk)
            time.sleep(0.4)
        if not rows:
            raise SeedError("SPARQL: " + "; ".join(errors) if errors else "пусто")
        if errors:
            print("sparql partial: " + "; ".join(errors), file=sys.stderr)
        records = _merge_rows(rows)
        for p31, _typed in queries_for_p31(query):
            for rec in records.values():
                if p31 in _p31(rec):
                    rec["p31"].add(p31)
    known_ids = {f"wd:{qid}" for qid in records}
    known_ids.update(row["id"] for row in existing_places if row.get("id"))
    known_ids.update(f"wd:{qid}" for qid in skip_map)
    for row in existing_places:
        wd = (row.get("wd") or "").strip()
        if wd.startswith("Q"):
            known_ids.add(f"wd:{wd}")
    hopped = 0
    if hop and from_json is None:
        if session is None:
            session = build_session()
        hopped = hop_unresolved(session, records, index, hop_batch)
    places, decls, applied = apply_harvest(
        records,
        index=index,
        existing_places=existing_places,
        existing_decls=existing_decls,
        today=today,
        skip_map=skip_map,
        known_ids=known_ids,
    )
    applied.hopped = hopped
    place_payload = dump_csv_bytes_or_raise(PLACES_HEADER, places, "cities-major.csv")
    decl_payload = dump_csv_bytes_or_raise(
        DECLENSIONS_HEADER, decls, "declensions/cities-major.csv"
    )
    applied.bytes_places = len(place_payload)
    applied.bytes_decl = len(decl_payload)
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
            write_csv(root / CITIES_REL, place_header, places)
            write_csv(root / DECL_REL, decl_header, decls)
    except SeedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    prefix = "dry-run" if args.dry_run else "ok"
    print(
        f"{prefix}\tincoming={counts.incoming}\tinserted={counts.inserted}"
        f"\tupdated={counts.updated}\tdeprecated={counts.deprecated}"
        f"\tskipped_parent={counts.skipped_parent}"
        f"\tskipped_overlap={counts.skipped_overlap}"
        f"\tskipped_other={counts.skipped_other}\thopped={counts.hopped}"
        f"\tdecl_added={counts.decl_added}"
        f"\tbytes_places={counts.bytes_places}\tbytes_decl={counts.bytes_decl}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
