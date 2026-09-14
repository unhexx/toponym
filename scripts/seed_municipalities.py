#!/usr/bin/env python3
"""Harvest Russian municipal formations from Wikidata into municipalities.csv.

Coverage is Wikidata P31 in the municipality allowlist, P17=Q159, not OKTMO/GAR.
SPARQL JSON/CSV is not vendored; optional --from-csv/--from-json is a cache
outside git. Daily sync stays known_ids_only (wikidata.yaml).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv  # noqa: E402
from scripts.lib.declensions import DECLENSIONS_HEADER  # noqa: E402
from scripts.lib.detectors import build_session  # noqa: E402
from scripts.lib.harvest import (  # noqa: E402
    ALIAS_FILL,
    FILL_IF_EMPTY,
    HarvestCounts,
    ParentHit,
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
SPARQL_PATH = Path("data/raw/wikidata/municipalities-ru.sparql")
MUN_REL = Path("data/curated/municipalities.csv")
DECL_REL = Path("data/declensions/municipalities.csv")
REGIONS_REL = Path("data/curated/regions.csv")
MUN_SPECS: tuple[tuple[Path, int], ...] = (
    (MUN_REL, 0),
    (REGIONS_REL, 1),
)
MUN_SKIP_RELS = (
    Path("data/curated/federal-districts.csv"),
    Path("data/curated/regions.csv"),
    Path("data/curated/cities-major.csv"),
    Path("data/curated/hydronyms-major.csv"),
    Path("data/curated/oronyms-major.csv"),
    Path("data/curated/hodonyms.csv"),
    Path("data/curated/microtoponyms.csv"),
    Path("data/curated/dromonyms.csv"),
    Path("data/curated/villages.csv"),
    Path("data/curated/agoronyms.csv"),
    Path("data/curated/agencies-foiv.csv"),
    Path("data/curated/agencies-other.csv"),
)
PASS1_P31 = frozenset(
    {"Q13626398", "Q3350075", "Q2198484", "Q60849925", "Q27587207"}
)
PASS2_P31 = frozenset({"Q2661988", "Q634099"})
ALL_P31 = PASS1_P31 | PASS2_P31
EXTRA_SCALARS = ("oktmo", "dissolved")
EXTRA_QID_SETS = ("replaced", "p31")
HOP_BATCH = 80
SHARD_WALL_SEC = 600
_VALUES_TYPE = re.compile(r"VALUES\s+\?type\s*\{[^}]+\}", re.IGNORECASE | re.DOTALL)
__all__ = [
    "MUN_SKIP_RELS",
    "MUN_SPECS",
    "apply_harvest",
    "harvest",
    "load_main_query",
    "load_parent_index",
    "main",
    "map_municipality",
    "oktmo_digits",
    "oktmo_lookup_keys",
    "p31_from_query",
    "queries_for_p31",
    "shard_query",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сиды МО из Wikidata SPARQL (не ГАР; не полный ОКТМО)"
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
    parser.add_argument(
        "--types",
        default="",
        help="подмножество P31 через запятую (Q13626398,Q3350075)",
    )
    parser.add_argument(
        "--shard-by-region",
        action="store_true",
        help="сразу шардить SPARQL по субъектам regions.csv",
    )
    return parser.parse_args(argv)


def parse_types(raw: str) -> frozenset[str] | None:
    text = (raw or "").strip()
    if not text:
        return None
    out: list[str] = []
    for part in text.split(","):
        qid = part.strip()
        if not qid:
            continue
        if qid.startswith("wd:"):
            qid = qid[3:]
        if not qid.startswith("Q"):
            qid = "Q" + qid
        out.append(qid)
    return frozenset(out) if out else None


def load_main_query(path: Path) -> str:
    return load_main_query_required(path, required=("SELECT", "VALUES", "?type"))


def queries_for_p31(query: str) -> list[tuple[str, str]]:
    return queries_for_p31_last(query, last=("Q634099",))


def load_parent_index(root: Path) -> ParentIndex:
    return load_parent_index_specs(root, MUN_SPECS)


def skip_ids(root: Path) -> dict[str, str]:
    return skip_ids_rels(root, MUN_SKIP_RELS)


def oktmo_digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def oktmo_lookup_keys(code: str) -> list[str]:
    digits = oktmo_digits(code)
    if not digits:
        return []
    keys = [digits]
    if len(digits) == 11 and digits[8:] == "000":
        keys.append(digits[:8])
    return keys


def shard_query(query: str, region_qid: str) -> str:
    match = _VALUES_TYPE.search(query)
    if match is None:
        raise SeedError("SPARQL: нет VALUES ?type для шарда")
    inject = (
        match.group(0)
        + f"\n  VALUES ?subj {{ wd:{region_qid} }}\n  ?item wdt:P131* ?subj ."
    )
    return query[: match.start()] + inject + query[match.end() :]


def region_wd_qids(root: Path) -> list[str]:
    path = root / REGIONS_REL
    if not path.is_file():
        return []
    _header, rows = read_csv(path)
    qids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        wd = (row.get("wd") or "").strip()
        if wd.startswith("Q") and wd not in seen:
            qids.append(wd)
            seen.add(wd)
    return qids


def map_municipality(
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
            "type_id": "municipality",
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


def _index_oktmo(index: dict[str, list[dict[str, str]]], row: dict[str, str]) -> None:
    rid = (row.get("id") or "").strip()
    if not rid:
        return
    for key in oktmo_lookup_keys(row.get("oktmo") or ""):
        bucket = index.setdefault(key, [])
        if all(item.get("id") != rid for item in bucket):
            bucket.append(row)


def _oktmo_hits(
    index: dict[str, list[dict[str, str]]], code: str
) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    seen: set[str] = set()
    for key in oktmo_lookup_keys(code):
        for row in index.get(key, []):
            rid = row.get("id") or ""
            if rid and rid not in seen:
                hits.append(row)
                seen.add(rid)
    return hits


def _prefer_replaced_by(
    replaced: set[str], known_ids: set[str], mun_ids: set[str]
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
        if ident in known_ids or ident in mun_ids:
            hits.append(ident)
    if not hits:
        return ""
    preferred = [ident for ident in hits if ident in mun_ids]
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
    hop_session: requests.Session | None = None,
    hop_batch: int = HOP_BATCH,
) -> tuple[list[dict[str, str]], list[dict[str, str]], HarvestCounts]:
    counts = HarvestCounts(incoming=len(records))
    original_ids = {row.get("id") for row in existing_places if row.get("id")}
    by_id = {row.get("id", ""): row for row in existing_places if row.get("id")}
    by_wd: dict[str, dict[str, str]] = {}
    for row in existing_places:
        wd = (row.get("wd") or "").strip()
        if wd.startswith("Q"):
            by_wd.setdefault(wd, row)
    oktmo_index: dict[str, list[dict[str, str]]] = {}
    for row in existing_places:
        _index_oktmo(oktmo_index, row)
    mun_ids = set(original_ids)
    for qid, rec in records.items():
        if qid in skip_map:
            continue
        if _p31(rec) & ALL_P31:
            mun_ids.add(f"wd:{qid}")
    incoming: list[dict[str, str]] = []
    new_places: list[dict[str, str]] = []

    def accept(inc: dict[str, str] | None, mapped: dict[str, str] | None) -> None:
        if mapped is not None:
            rid = mapped["id"]
            by_id[rid] = mapped
            wd = (mapped.get("wd") or "").strip()
            if wd.startswith("Q"):
                by_wd.setdefault(wd, mapped)
            _index_oktmo(oktmo_index, mapped)
            mun_ids.add(rid)
            if rid not in original_ids and rid not in {place["id"] for place in new_places}:
                new_places.append(mapped)
        if inc is None:
            return
        incoming.append(inc)

    def process(qid: str, rec: dict[str, Any]) -> dict[str, str] | None:
        ru = str(rec.get("ru") or "").strip()
        if not ru:
            counts.skipped_other += 1
            return None
        if qid in skip_map:
            counts.skipped_overlap += 1
            print(f"skip overlap wd:{qid} table={skip_map[qid]}", file=sys.stderr)
            return None
        status, existing = _lookup_existing(qid, by_id, by_wd)
        if status == "overlap":
            counts.skipped_overlap += 1
            print(f"skip overlap wd:{qid} table=municipalities", file=sys.stderr)
            return None
        dissolved = bool(str(rec.get("dissolved") or "").strip())
        if dissolved and existing is None:
            counts.skipped_other += 1
            return None
        if dissolved and existing is not None:
            replaced = _prefer_replaced_by(
                {str(item) for item in (rec.get("replaced") or set())},
                known_ids,
                mun_ids,
            )
            accept(incoming_deprecate(existing["id"], replaced, today), None)
            return None
        parent = resolve_parent(index, rec.get("located") or set(), rec.get("iso") or set())
        if parent is None:
            counts.skipped_parent += 1
            return None
        mapped = map_municipality(rec, parent, today)
        if mapped["id"].startswith("gn:"):
            counts.skipped_other += 1
            return None
        if existing is not None:
            others = [
                hit
                for hit in _oktmo_hits(oktmo_index, mapped["oktmo"])
                if hit.get("id") != existing.get("id")
            ]
            if others:
                counts.skipped_overlap += 1
                print(f"skip overlap wd:{qid} table=municipalities", file=sys.stderr)
                return None
            mapped["id"] = existing["id"]
            fill = ALIAS_FILL if existing["id"].startswith("local:") else FILL_IF_EMPTY
            accept(incoming_for_upsert(mapped, existing, fill=fill), mapped)
            return mapped
        hits = _oktmo_hits(oktmo_index, mapped["oktmo"])
        if len(hits) >= 2:
            counts.skipped_overlap += 1
            print(f"skip overlap wd:{qid} table=municipalities", file=sys.stderr)
            return None
        if len(hits) == 1:
            alias = hits[0]
            mapped["id"] = alias["id"]
            accept(incoming_for_upsert(mapped, alias, fill=ALIAS_FILL), mapped)
            return mapped
        accept(incoming_for_upsert(mapped, None, fill=FILL_IF_EMPTY), mapped)
        return mapped

    pass1 = {qid: rec for qid, rec in records.items() if _p31(rec) & PASS1_P31}
    pass2 = {
        qid: rec
        for qid, rec in records.items()
        if qid not in pass1 and _p31(rec) & PASS2_P31
    }
    for qid, rec in records.items():
        if qid not in pass1 and qid not in pass2:
            counts.skipped_other += 1

    if hop_session is not None:
        counts.hopped += hop_unresolved(hop_session, records, index, hop_batch)
    for qid, rec in pass1.items():
        mapped = process(qid, rec)
        if mapped is None:
            continue
        index.by_wd.setdefault(
            qid, ParentHit(id=mapped["id"], admin1=mapped.get("admin1") or "", rank=0)
        )
    if hop_session is not None:
        counts.hopped += hop_unresolved(hop_session, records, index, hop_batch)
    for qid, rec in pass2.items():
        process(qid, rec)

    places, upsert_counts = upsert_rows(existing_places, incoming, header=PLACES_HEADER)
    counts.inserted = upsert_counts.inserted
    counts.updated = upsert_counts.updated
    counts.deprecated = upsert_counts.deprecated
    decl_seen = {(row.get("id"), row.get("lemma")) for row in existing_decls}
    decls = [dict(row) for row in existing_decls]
    for place in new_places:
        if place["id"] in original_ids:
            continue
        stub = declension_stub(place, type_code="municipality")
        key = (stub["id"], stub["lemma"])
        if key in decl_seen:
            continue
        decls.append(stub)
        decl_seen.add(key)
        counts.decl_added += 1
    return places, decls, counts


def _merge_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    return merge_bindings(rows, extra_scalars=EXTRA_SCALARS, extra_qid_sets=EXTRA_QID_SETS)


def _filter_types(
    records: dict[str, dict[str, Any]], types: frozenset[str] | None
) -> dict[str, dict[str, Any]]:
    if not types:
        return records
    return {qid: rec for qid, rec in records.items() if _p31(rec) & types}


def _fetch_sharded(
    session: requests.Session,
    p31: str,
    typed: str,
    root: Path,
    started: float,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    failed = 0
    for region_qid in region_wd_qids(root):
        if time.monotonic() - started > SHARD_WALL_SEC:
            print(
                f"sparql partial: {p31} shards failed={failed}",
                file=sys.stderr,
            )
            break
        query = shard_query(typed, region_qid)
        try:
            chunk = sparql_csv(session, query, timeout=60)
        except SeedError:
            failed += 1
            time.sleep(0.4)
            continue
        rows.extend(chunk)
        time.sleep(0.4)
    if failed:
        print(f"sparql partial: {p31} shards failed={failed}", file=sys.stderr)
    return rows


def _fetch_p31(
    session: requests.Session,
    p31: str,
    typed: str,
    *,
    root: Path,
    force_shard: bool,
    started: float,
) -> list[dict[str, str]]:
    if not force_shard:
        for _attempt in range(2):
            print(f"sparql P31={p31}", file=sys.stderr)
            try:
                chunk = sparql_csv(session, typed, timeout=90)
            except SeedError as exc:
                print(f"sparql P31={p31} fail {exc}", file=sys.stderr)
                continue
            print(f"sparql P31={p31} rows={len(chunk)}", file=sys.stderr)
            return chunk
    print(f"sparql P31={p31} shard-by-region", file=sys.stderr)
    return _fetch_sharded(session, p31, typed, root, started)


def harvest(
    *,
    root: Path,
    today: str,
    from_json: Path | None,
    from_csv: Path | None,
    hop: bool,
    hop_batch: int,
    types: frozenset[str] | None = None,
    shard_by_region: bool = False,
    session: requests.Session | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]], HarvestCounts, list[str], list[str]]:
    place_header, existing_places = read_table(root / MUN_REL, PLACES_HEADER)
    decl_header, existing_decls = read_table(root / DECL_REL, DECLENSIONS_HEADER)
    if place_header and place_header != PLACES_HEADER:
        raise SeedError(f"municipalities.csv: заголовок {place_header}")
    if decl_header and decl_header != DECLENSIONS_HEADER:
        raise SeedError(f"declensions/municipalities.csv: заголовок {decl_header}")
    index = load_parent_index(root)
    skip_map = skip_ids(root)
    started = time.monotonic()
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
        pairs = queries_for_p31(query)
        if types:
            pairs = [(p31, typed) for p31, typed in pairs if p31 in types]
            if not pairs:
                raise SeedError("нет P31 из --types в SPARQL")
        rows = []
        errors: list[str] = []
        for p31, typed in pairs:
            try:
                chunk = _fetch_p31(
                    session,
                    p31,
                    typed,
                    root=root,
                    force_shard=shard_by_region,
                    started=started,
                )
            except SeedError as exc:
                errors.append(f"{p31}: {exc}")
                print(f"sparql P31={p31} fail {exc}", file=sys.stderr)
                continue
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
        for p31, _typed in pairs:
            for rec in records.values():
                if p31 in _p31(rec):
                    rec["p31"].add(p31)
    records = _filter_types(records, types)
    known_ids = {f"wd:{qid}" for qid in records}
    known_ids.update(row["id"] for row in existing_places if row.get("id"))
    known_ids.update(f"wd:{qid}" for qid in skip_map)
    for row in existing_places:
        wd = (row.get("wd") or "").strip()
        if wd.startswith("Q"):
            known_ids.add(f"wd:{wd}")
    do_hop = hop and from_json is None
    if do_hop and session is None:
        session = build_session()
    places, decls, applied = apply_harvest(
        records,
        index=index,
        existing_places=existing_places,
        existing_decls=existing_decls,
        today=today,
        skip_map=skip_map,
        known_ids=known_ids,
        hop_session=session if do_hop else None,
        hop_batch=hop_batch,
    )
    place_payload = dump_csv_bytes_or_raise(PLACES_HEADER, places, "municipalities.csv")
    decl_payload = dump_csv_bytes_or_raise(
        DECLENSIONS_HEADER, decls, "declensions/municipalities.csv"
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
            types=parse_types(args.types),
            shard_by_region=args.shard_by_region,
        )
        if not args.dry_run:
            write_csv(root / MUN_REL, place_header, places)
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
