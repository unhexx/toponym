#!/usr/bin/env python3
"""Harvest Russian streets from Wikidata SPARQL into data/curated/hodonyms.csv.

Coverage is Wikidata (P31=Q79007, P17=Q159), not FIAS/GAR. SPARQL JSON/CSV
is not vendored; optional --from-csv/--from-json is a cache outside git.
Daily sync stays known_ids_only (data/mappings/wikidata.yaml).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.csvio import PLACES_HEADER, dump_csv_bytes, read_csv, write_csv  # noqa: E402
from scripts.lib.declensions import DECLENSIONS_HEADER  # noqa: E402
from scripts.lib.detectors import USER_AGENT, build_session  # noqa: E402
from scripts.lib.invariants import yo_to_e  # noqa: E402
from scripts.lib.upsert import DEFAULT_MAX_VENDOR_BYTES, too_large, upsert_rows  # noqa: E402

ROOT = _ROOT
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
SPARQL_PATH = Path("data/raw/wikidata/hodonyms-ru.sparql")
HODONYMS_REL = Path("data/curated/hodonyms.csv")
DECL_REL = Path("data/declensions/hodonyms.csv")
CITIES_REL = Path("data/curated/cities-major.csv")
REGIONS_REL = Path("data/curated/regions.csv")
MUN_REL = Path("data/curated/municipalities.csv")
AGORONYMS_REL = Path("data/curated/agoronyms.csv")
DROMONYMS_REL = Path("data/curated/dromonyms.csv")
HOP_BATCH = 80
HOP_QUERY = """SELECT DISTINCT ?item ?subj ?iso WHERE {
  VALUES ?item { %s }
  ?item wdt:P131* ?subj .
  ?subj wdt:P300 ?iso .
  FILTER(STRSTARTS(?iso, "RU-"))
}
"""
FILL_IF_EMPTY = ("lat", "lon", "geonames", "name_en", "admin1", "parent_id", "name_yo")


class SeedError(Exception):
    pass


@dataclass
class ParentHit:
    id: str
    admin1: str
    rank: int


@dataclass
class ParentIndex:
    by_wd: dict[str, ParentHit] = field(default_factory=dict)
    by_iso: dict[str, ParentHit] = field(default_factory=dict)


@dataclass
class HarvestCounts:
    incoming: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_parent: int = 0
    skipped_square: int = 0
    skipped_other: int = 0
    decl_added: int = 0
    hopped: int = 0


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


def qid_from_uri(value: str) -> str:
    text = (value or "").strip()
    if text.startswith("wd:"):
        text = text[3:]
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    if len(text) > 1 and text[0] in {"Q", "q"} and text[1:].isdigit():
        return "Q" + text[1:]
    return ""


def format_coord(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return ""
    if not math.isfinite(number):
        return ""
    return f"{number:.8f}".rstrip("0").rstrip(".")


def is_square_name(name: str) -> bool:
    return "площадь" in (name or "").casefold()


def load_main_query(path: Path) -> str:
    lines: list[str] = []
    started = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not started:
            if stripped.startswith("SELECT"):
                started = True
            else:
                continue
        if stripped.startswith("#"):
            break
        lines.append(raw)
    query = "\n".join(lines).strip()
    if "SELECT" not in query or "Q79007" not in query:
        raise SeedError(f"нет основного SPARQL в {path}")
    return query


def _cell(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def merge_bindings(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        qid = qid_from_uri(_cell(row, "item", "qid"))
        if not qid:
            continue
        rec = out.setdefault(
            qid,
            {
                "qid": qid,
                "ru": "",
                "en": "",
                "lat": "",
                "lon": "",
                "gn": "",
                "located": set(),
                "iso": set(),
            },
        )
        ru = _cell(row, "ru", "label_ru")
        if ru and not rec["ru"]:
            rec["ru"] = ru
        en = _cell(row, "en", "label_en")
        if en and not rec["en"]:
            rec["en"] = en
        lat = format_coord(_cell(row, "lat", "P625_lat"))
        lon = format_coord(_cell(row, "lon", "P625_lon"))
        if lat and lon and not rec["lat"]:
            rec["lat"] = lat
            rec["lon"] = lon
        gn = "".join(ch for ch in _cell(row, "gn", "geonames", "P1566") if ch.isdigit())
        if gn and not rec["gn"]:
            rec["gn"] = gn
        for key in ("located", "locatedUp", "subj"):
            loc = qid_from_uri(_cell(row, key))
            if loc:
                rec["located"].add(loc)
        for key in ("iso", "isoUp"):
            iso = _cell(row, key)
            if iso.startswith("RU-"):
                rec["iso"].add(iso)
    return out


def load_parent_index(root: Path) -> ParentIndex:
    index = ParentIndex()
    specs = (
        (CITIES_REL, 0),
        (MUN_REL, 1),
        (REGIONS_REL, 2),
    )
    for rel, rank in specs:
        path = root / rel
        if not path.is_file():
            continue
        _header, rows = read_csv(path)
        for row in rows:
            ident = (row.get("id") or "").strip()
            if not ident:
                continue
            admin1 = (row.get("admin1") or row.get("iso") or "").strip()
            hit = ParentHit(id=ident, admin1=admin1, rank=rank)
            wd = (row.get("wd") or "").strip()
            if wd.startswith("Q"):
                index.by_wd.setdefault(wd, hit)
            iso = (row.get("iso") or "").strip()
            if iso.startswith("RU-"):
                index.by_iso.setdefault(iso, hit)
    return index


def resolve_parent(
    index: ParentIndex, located: set[str], isos: set[str]
) -> tuple[str, str] | None:
    ranked: list[tuple[int, str, str]] = []
    for qid in located:
        hit = index.by_wd.get(qid)
        if hit:
            ranked.append((hit.rank, hit.id, hit.admin1))
    if ranked:
        ranked.sort()
        if ranked[0][0] <= 1:
            return ranked[0][1], ranked[0][2]
    for iso in isos:
        hit = index.by_iso.get(iso)
        if hit:
            ranked.append((hit.rank, hit.id, hit.admin1))
    if not ranked:
        return None
    ranked.sort()
    return ranked[0][1], ranked[0][2]


def skip_ids(root: Path) -> set[str]:
    out: set[str] = set()
    for rel in (AGORONYMS_REL, DROMONYMS_REL):
        path = root / rel
        if not path.is_file():
            continue
        _header, rows = read_csv(path)
        for row in rows:
            wd = (row.get("wd") or "").strip()
            if wd.startswith("Q"):
                out.add(wd)
            rid = (row.get("id") or "").strip()
            if rid.startswith("wd:"):
                out.add(rid[3:])
    return out


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


def incoming_for_upsert(
    mapped: dict[str, str],
    existing: dict[str, str] | None,
) -> dict[str, str] | None:
    if existing is None:
        return mapped
    inc = {"id": mapped["id"]}
    for key in FILL_IF_EMPTY:
        if not (existing.get(key) or "") and (mapped.get(key) or ""):
            inc[key] = mapped[key]
    if len(inc) == 1:
        return None
    return inc


def declension_stub(place: dict[str, str]) -> dict[str, str]:
    row = {key: "" for key in DECLENSIONS_HEADER}
    row.update(
        {
            "id": place["id"],
            "type_code": "hodonym",
            "lemma": place["name_ru"],
            "yo": place.get("name_yo") or "",
            "paradigm": "mixed_phrase",
            "declinable": "always",
            "nom": place["name_ru"],
            "review": "needs_review",
            "source": "wikidata",
        }
    )
    return row


def _read_table(path: Path, header: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        return header, []
    got_header, rows = read_csv(path)
    return got_header or header, rows


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


def load_rows_from_json(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        bindings = payload.get("results", {}).get("bindings") or payload.get("rows") or []
        rows: list[dict[str, str]] = []
        for raw in bindings:
            if not isinstance(raw, dict):
                continue
            flat: dict[str, str] = {}
            for key, value in raw.items():
                if isinstance(value, dict):
                    flat[key] = str(value.get("value") or "")
                else:
                    flat[key] = str(value or "")
            rows.append(flat)
        return rows
    if isinstance(payload, list):
        return [{str(k): "" if v is None else str(v) for k, v in row.items()} for row in payload]
    raise SeedError("JSON: нужен список строк или SPARQL results")


def load_rows_from_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def sparql_csv(session: requests.Session, query: str, timeout: int = 90) -> list[dict[str, str]]:
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(
                SPARQL_ENDPOINT,
                params={"query": query},
                headers={"Accept": "text/csv", "User-Agent": USER_AGENT},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            last = SeedError(str(exc))
            time.sleep(2**attempt)
            continue
        if response.status_code in {429, 502, 503, 504}:
            last = SeedError(f"SPARQL HTTP {response.status_code}")
            time.sleep(2**attempt)
            continue
        if response.status_code >= 400:
            raise SeedError(f"SPARQL HTTP {response.status_code}: {response.text[:300]}")
        text = response.text
        if not text.strip():
            return []
        if text.lstrip().startswith("{") and "error" in text[:400].casefold():
            raise SeedError(f"SPARQL error: {text[:300]}")
        return list(csv.DictReader(io.StringIO(text)))
    raise last or SeedError("SPARQL: нет ответа")


def hop_unresolved(
    session: requests.Session,
    records: dict[str, dict[str, Any]],
    index: ParentIndex,
    batch_size: int,
) -> int:
    pending = [
        qid
        for qid, rec in records.items()
        if resolve_parent(index, rec["located"], rec["iso"]) is None
    ]
    if not pending:
        return 0
    hopped = 0
    size = max(1, batch_size)
    total = len(pending)
    for offset in range(0, total, size):
        if offset == 0 or ((offset // size) % 10 == 0):
            print(f"hop {offset}/{total}", file=sys.stderr)
        chunk = pending[offset : offset + size]
        values = " ".join(f"wd:{qid}" for qid in chunk)
        rows = sparql_csv(session, HOP_QUERY % values, timeout=60)
        extra = merge_bindings(rows)
        for qid, rec in extra.items():
            target = records.get(qid)
            if target is None:
                continue
            before = (set(target["located"]), set(target["iso"]))
            target["located"].update(rec["located"])
            target["iso"].update(rec["iso"])
            if (target["located"], target["iso"]) != before:
                hopped += 1
        time.sleep(0.15)
    return hopped


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
    place_header, existing_places = _read_table(root / HODONYMS_REL, PLACES_HEADER)
    decl_header, existing_decls = _read_table(root / DECL_REL, DECLENSIONS_HEADER)
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
        rows = sparql_csv(session, query, timeout=90)
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
    payload = dump_csv_bytes(PLACES_HEADER, places)
    if too_large(len(payload)):
        raise SeedError(
            f"hodonyms.csv {len(payload)} байт > {DEFAULT_MAX_VENDOR_BYTES} (не вендорить дамп)"
        )
    return places, decls, applied, PLACES_HEADER, DECLENSIONS_HEADER


def utc_today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


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
