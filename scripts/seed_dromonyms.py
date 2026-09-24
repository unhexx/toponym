#!/usr/bin/env python3
"""Harvest Russian roads and railways from Wikidata into dromonyms.csv.

Coverage is Wikidata P31=Q34442 (road) and P31=Q728937 (railway, ruwiki),
P17=Q159, not the official federal highway list (ПП № 928) and not OSM.
SPARQL JSON/CSV is not vendored; optional --from-csv/--from-json is a cache
outside git. Daily sync stays known_ids_only (wikidata.yaml).
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
    hop_unresolved,
    incoming_for_upsert,
    load_rows_from_csv,
    load_rows_from_json,
    merge_bindings,
    p31_from_query,
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
SPARQL_PATH = Path("data/raw/wikidata/dromonyms-ru.sparql")
DRO_REL = Path("data/curated/dromonyms.csv")
DECL_REL = Path("data/declensions/dromonyms.csv")
CITIES_REL = Path("data/curated/cities-major.csv")
REGIONS_REL = Path("data/curated/regions.csv")
DRO_SPECS: tuple[tuple[Path, int], ...] = (
    (REGIONS_REL, 0),
    (CITIES_REL, 1),
)
DRO_SKIP_RELS = (
    Path("data/curated/federal-districts.csv"),
    Path("data/curated/regions.csv"),
    Path("data/curated/cities-major.csv"),
    Path("data/curated/hydronyms-major.csv"),
    Path("data/curated/oronyms-major.csv"),
    Path("data/curated/hodonyms.csv"),
    Path("data/curated/microtoponyms.csv"),
    Path("data/curated/villages.csv"),
    Path("data/curated/agoronyms.csv"),
    Path("data/curated/municipalities.csv"),
    Path("data/curated/agencies-foiv.csv"),
    Path("data/curated/agencies-other.csv"),
)
EXTRA_QID_SETS = ("p31",)
HOP_BATCH = 80
__all__ = [
    "DRO_SKIP_RELS",
    "DRO_SPECS",
    "apply_harvest",
    "harvest",
    "load_main_query",
    "load_parent_index",
    "main",
    "map_dromonym",
    "p31_from_query",
    "queries_for_p31",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сиды дорог и ЖД из Wikidata SPARQL (не ПП № 928, не OSM)"
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
        path, required=("SELECT", "VALUES", "?type", "Q34442", "Q728937")
    )


def queries_for_p31(query: str) -> list[tuple[str, str]]:
    return queries_for_p31_last(query, last=("Q728937",))


def load_parent_index(root: Path) -> ParentIndex:
    return load_parent_index_specs(root, DRO_SPECS)


def skip_ids(root: Path) -> dict[str, str]:
    return skip_ids_rels(root, DRO_SKIP_RELS)


def map_dromonym(
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
            "type_id": "dromonym",
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


# Ложный родитель из несвязанного OPTIONAL: меньший iso или Москва.
BOGUS_PARENTS = frozenset({"iso:RU-AD", "wd:Q649"})


def _candidate_rows(
    index: ParentIndex,
    located: set[str],
    isos: set[str],
) -> list[tuple[int, str, str]]:
    """Тот же порядок, что у resolve_parent, но без выбора одного id."""
    ranked: list[tuple[int, str, str]] = []
    for qid in located:
        hit = index.by_wd.get(qid)
        if hit:
            ranked.append((hit.rank, hit.id, hit.admin1))
    if ranked:
        ranked.sort()
        if ranked[0][0] <= 1:
            return ranked
    for iso in isos:
        hit = index.by_iso.get(iso)
        if hit:
            ranked.append((hit.rank, hit.id, hit.admin1))
    ranked.sort()
    return ranked


def _same_rank_tie(ranked: list[tuple[int, str, str]]) -> bool:
    if not ranked:
        return False
    best = ranked[0][0]
    return len({item[1] for item in ranked if item[0] == best}) > 1


def _merge_parent_refresh(
    inc: dict[str, str] | None,
    mapped: dict[str, str],
    existing: dict[str, str],
) -> dict[str, str] | None:
    """Снять или сменить parent, если новый разбор не совпал с CSV.

    Fill-if-empty не затирает ложные iso:RU-AD и wd:Q649.
    """
    if (existing.get("id") or "").startswith("local:"):
        return inc
    parent_id = mapped.get("parent_id") or ""
    admin1 = mapped.get("admin1") or ""
    if parent_id == (existing.get("parent_id") or "") and admin1 == (existing.get("admin1") or ""):
        return inc
    if inc is None:
        inc = {"id": mapped["id"]}
    inc["parent_id"] = parent_id
    inc["admin1"] = admin1
    inc["updated_at"] = mapped.get("updated_at") or ""
    return inc


def _parent_for_refresh(
    existing: dict[str, str] | None,
    resolved: tuple[str, str] | None,
) -> tuple[str, str] | None:
    """Пустой parent у уже записанной дороги, если разбор не дал одного родителя.

    Ложные iso:RU-AD и wd:Q649 снимаются. Несколько субъектов одного ранга
    не схлопываются в меньший iso. Уже выбранный неложный родитель не
    подменяется. Новая дорога без одного родителя по-прежнему пропускается.
    """
    if existing is None or (existing.get("id") or "").startswith("local:"):
        return resolved
    old = (existing.get("parent_id") or "", existing.get("admin1") or "")
    if resolved is None:
        if old[0] in BOGUS_PARENTS:
            return ("", "")
        return old
    if old[0] and old[0] not in BOGUS_PARENTS and old[0] != resolved[0]:
        return old
    return resolved


def apply_harvest(
    records: dict[str, dict[str, Any]],
    *,
    index: ParentIndex,
    existing_places: list[dict[str, str]],
    existing_decls: list[dict[str, str]],
    today: str,
    skip_map: dict[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], HarvestCounts]:
    counts = HarvestCounts(incoming=len(records))
    original_ids = {row.get("id") for row in existing_places if row.get("id")}
    by_id = {row.get("id", ""): row for row in existing_places if row.get("id")}
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
        existing = by_id.get(f"wd:{qid}")
        located = rec.get("located") or set()
        isos = rec.get("iso") or set()
        ranked = _candidate_rows(index, located, isos)
        resolved = None if _same_rank_tie(ranked) else resolve_parent(index, located, isos)
        if resolved is None and (
            existing is None or (existing.get("id") or "").startswith("local:")
        ):
            counts.skipped_parent += 1
            continue
        parent = _parent_for_refresh(existing, resolved)
        if parent is None:
            counts.skipped_parent += 1
            continue
        mapped = map_dromonym(rec, parent, today)
        if mapped["id"].startswith("gn:"):
            counts.skipped_other += 1
            continue
        if existing is not None:
            mapped["id"] = existing["id"]
            inc = incoming_for_upsert(mapped, existing)
            inc = _merge_parent_refresh(inc, mapped, existing)
            if inc is not None:
                incoming.append(inc)
            continue
        inc = incoming_for_upsert(mapped, None)
        if inc is None:
            continue
        incoming.append(inc)
        new_places.append(mapped)
    places, upsert_counts = upsert_rows(existing_places, incoming, header=PLACES_HEADER)
    counts.inserted = upsert_counts.inserted
    counts.updated = upsert_counts.updated
    counts.deprecated = upsert_counts.deprecated
    decl_seen = {(row.get("id"), row.get("lemma")) for row in existing_decls}
    decls = [dict(row) for row in existing_decls]
    for place in new_places:
        if place["id"] in original_ids:
            continue
        stub = declension_stub(place, type_code="dromonym")
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
    place_header, existing_places = read_table(root / DRO_REL, PLACES_HEADER)
    decl_header, existing_decls = read_table(root / DECL_REL, DECLENSIONS_HEADER)
    if place_header and place_header != PLACES_HEADER:
        raise SeedError(f"dromonyms.csv: заголовок {place_header}")
    if decl_header and decl_header != DECLENSIONS_HEADER:
        raise SeedError(f"declensions/dromonyms.csv: заголовок {decl_header}")
    index = load_parent_index(root)
    skip_map = skip_ids(root)
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
    records = merge_bindings(rows, extra_qid_sets=EXTRA_QID_SETS)
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
    )
    applied.hopped = hopped
    place_payload = dump_csv_bytes_or_raise(PLACES_HEADER, places, "dromonyms.csv")
    decl_payload = dump_csv_bytes_or_raise(
        DECLENSIONS_HEADER, decls, "declensions/dromonyms.csv"
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
            write_csv(root / DRO_REL, place_header, places)
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
