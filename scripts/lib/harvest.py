"""Parameterized Wikidata SPARQL harvest helpers.

Hodonym/municipality/microtoponym CLIs pass required/last/specs/rels/fill.
SPARQL JSON/CSV is not vendored; dumps over 10 MB are refused.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from scripts.lib.csvio import dump_csv_bytes, read_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.detectors import USER_AGENT
from scripts.lib.invariants import yo_to_e
from scripts.lib.upsert import DEFAULT_MAX_VENDOR_BYTES, too_large

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HOP_QUERY = """SELECT DISTINCT ?item ?subj ?iso WHERE {
  VALUES ?item { %s }
  ?item wdt:P131* ?subj .
  ?subj wdt:P300 ?iso .
  FILTER(STRSTARTS(?iso, "RU-"))
}
"""
KNOWN_IDS_QUERY = """SELECT DISTINCT ?item ?ru ?en ?lat ?lon ?gn ?oktmo WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item rdfs:label ?ru FILTER(LANG(?ru) = "ru") }
  OPTIONAL { ?item rdfs:label ?en FILTER(LANG(?en) = "en") }
  OPTIONAL { ?item p:P625/psv:P625 [ wikibase:geoLatitude ?lat; wikibase:geoLongitude ?lon ] }
  OPTIONAL { ?item wdt:P1566 ?gn }
  OPTIONAL { ?item wdt:P764 ?oktmo }
}
"""
LOCATED_QUERY = """SELECT DISTINCT ?item ?located ?iso WHERE {
  VALUES ?item { %s }
  ?item wdt:P131* ?located .
  OPTIONAL { ?located wdt:P300 ?iso FILTER(STRSTARTS(?iso, "RU-")) }
}
"""
FILL_IF_EMPTY = ("lat", "lon", "geonames", "name_en", "admin1", "parent_id", "name_yo")
ALIAS_FILL = ("wd", "lat", "lon", "geonames", "name_en")
KNOWN_FILL = ("lat", "lon", "geonames", "name_en", "oktmo", "wd", "name_yo")
KNOWN_IDS_BATCH = 80
REGIONS_REL = Path("data/curated/regions.csv")
_VALUES_TYPE = re.compile(r"VALUES\s+\?type\s*\{([^}]+)\}", re.IGNORECASE | re.DOTALL)
_WD_QID = re.compile(r"wd:(Q\d+)", re.IGNORECASE)
_QID_SET_ALIASES = {
    "p31": ("p31", "type"),
}


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
    deprecated: int = 0
    skipped_overlap: int = 0
    bytes_places: int = 0
    bytes_decl: int = 0


def qid_from_uri(value: str) -> str:
    text = (value or "").strip()
    if text.startswith("wd:"):
        text = text[3:]
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    if len(text) > 1 and text[0] in {"Q", "q"} and text[1:].isdigit():
        return "Q" + text[1:]
    return ""


def qid_of_place(row: dict[str, str]) -> str:
    return qid_from_uri(row.get("wd") or "") or qid_from_uri(row.get("id") or "")


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


def load_main_query(
    path: Path, required: tuple[str, ...] = ("SELECT", "VALUES", "?type")
) -> str:
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
    if not query or "SELECT" not in query:
        raise SeedError(f"нет основного SPARQL в {path}")
    missing = [needle for needle in required if needle not in query]
    if missing:
        if "VALUES" in missing or "?type" in missing:
            raise SeedError(f"SPARQL без VALUES ?type в {path}")
        raise SeedError(f"нет основного SPARQL в {path}")
    return query


def p31_from_query(query: str) -> list[str]:
    match = _VALUES_TYPE.search(query)
    if match:
        qids: list[str] = []
        for raw in _WD_QID.findall(match.group(1)):
            qid = "Q" + raw[1:]
            if qid not in qids:
                qids.append(qid)
        if qids:
            return qids
    raise SeedError("SPARQL: нет P31 в VALUES ?type")


def queries_for_p31(query: str, last: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    types = p31_from_query(query)
    last_set = set(last)
    types = [qid for qid in types if qid not in last_set] + [
        qid for qid in types if qid in last_set
    ]
    match = _VALUES_TYPE.search(query)
    if match is None:
        return [(types[0], query)]
    out: list[tuple[str, str]] = []
    for qid in types:
        typed = query[: match.start()] + f"VALUES ?type {{ wd:{qid} }}" + query[match.end() :]
        out.append((qid, typed))
    return out


def _cell(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def merge_bindings(
    rows: list[dict[str, str]],
    extra_scalars: tuple[str, ...] = (),
    extra_qid_sets: tuple[str, ...] = (),
) -> dict[str, dict[str, Any]]:
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
        for key in extra_scalars:
            rec.setdefault(key, "")
        for key in extra_qid_sets:
            rec.setdefault(key, set())
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
        for key in extra_scalars:
            value = _cell(row, key)
            if value and not rec[key]:
                rec[key] = value
        for key in extra_qid_sets:
            aliases = _QID_SET_ALIASES.get(key, (key,))
            for alias in aliases:
                extra = qid_from_uri(_cell(row, alias))
                if extra:
                    rec[key].add(extra)
    return out


def load_parent_index(root: Path, specs: tuple[tuple[Path, int], ...]) -> ParentIndex:
    index = ParentIndex()
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


def skip_ids(root: Path, rels: tuple[Path, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in rels:
        path = root / rel
        if not path.is_file():
            continue
        name = Path(rel).stem
        _header, rows = read_csv(path)
        for row in rows:
            wd = (row.get("wd") or "").strip()
            if wd.startswith("Q"):
                out.setdefault(wd, name)
            rid = (row.get("id") or "").strip()
            if rid.startswith("wd:"):
                out.setdefault(rid[3:], name)
    return out


def incoming_for_upsert(
    mapped: dict[str, str],
    existing: dict[str, str] | None,
    fill: tuple[str, ...] = FILL_IF_EMPTY,
) -> dict[str, str] | None:
    if existing is None:
        return mapped
    inc = {"id": mapped["id"]}
    for key in fill:
        if not (existing.get(key) or "") and (mapped.get(key) or ""):
            inc[key] = mapped[key]
    if len(inc) == 1:
        return None
    return inc


def incoming_deprecate(existing_id: str, replaced_by: str, today: str) -> dict[str, str]:
    row = {"id": existing_id, "status": "deprecated", "updated_at": today}
    if replaced_by:
        row["replaced_by"] = replaced_by
    return row


def declension_stub(place: dict[str, str], type_code: str = "hodonym") -> dict[str, str]:
    row = {key: "" for key in DECLENSIONS_HEADER}
    row.update(
        {
            "id": place["id"],
            "type_code": type_code,
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


def read_table(path: Path, header: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        return header, []
    got_header, rows = read_csv(path)
    return got_header or header, rows


def dump_csv_bytes_or_raise(header: list[str], rows: list[dict[str, str]], label: str) -> bytes:
    payload = dump_csv_bytes(header, rows)
    if too_large(len(payload)):
        raise SeedError(
            f"{label} {len(payload)} байт > {DEFAULT_MAX_VENDOR_BYTES} (не вендорить дамп)"
        )
    return payload


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


def shard_query(query: str, region_qid: str) -> str:
    match = _VALUES_TYPE.search(query)
    if match is None:
        raise SeedError("SPARQL: нет VALUES ?type для шарда")
    inject = (
        match.group(0)
        + f"\n  VALUES ?subj {{ wd:{region_qid} }}\n  ?item wdt:P131* ?subj ."
    )
    return query[: match.start()] + inject + query[match.end() :]


def region_wd_qids(root: Path, rel: Path = REGIONS_REL) -> list[str]:
    path = root / rel
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


def fetch_sharded(
    session: requests.Session | None,
    typed: str,
    region_qids: list[str],
    *,
    wall_sec: float = 0,
    timeout: int = 60,
    p31: str = "",
    started: float | None = None,
    fetch: Callable[[str], list[dict[str, str]]] | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    failed = 0
    if started is None:
        started = time.monotonic()

    def default_fetch(region_qid: str) -> list[dict[str, str]]:
        if session is None:
            raise SeedError("SPARQL: нет сессии для шарда")
        return sparql_csv(
            session, shard_query(typed, region_qid), timeout=timeout
        )

    getter = fetch if fetch is not None else default_fetch
    for region_qid in region_qids:
        if wall_sec > 0 and time.monotonic() - started > wall_sec:
            print(
                f"sparql partial: {p31} shards failed={failed}",
                file=sys.stderr,
            )
            break
        try:
            chunk = getter(region_qid)
        except SeedError:
            failed += 1
            if fetch is None:
                time.sleep(0.4)
            continue
        rows.extend(chunk)
        if fetch is None:
            time.sleep(0.4)
    if failed:
        print(
            f"sparql partial: {p31} shards failed={failed}",
            file=sys.stderr,
        )
    return rows


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


def fetch_located(
    session: requests.Session,
    qids: list[str],
    batch_size: int,
) -> dict[str, dict[str, Any]]:
    """P131* ancestors so a harvested район can parent a street in a settlement."""
    if not qids:
        return {}
    size = max(1, int(batch_size))
    out: dict[str, dict[str, Any]] = {}
    total = len(qids)
    for offset in range(0, total, size):
        if offset == 0 or ((offset // size) % 10 == 0):
            print(f"p131 {offset}/{total}", file=sys.stderr)
        chunk = qids[offset : offset + size]
        values = " ".join(f"wd:{qid}" for qid in chunk)
        try:
            rows = sparql_csv(session, LOCATED_QUERY % values, timeout=60)
        except SeedError as exc:
            print(f"p131 fail offset={offset} {exc}", file=sys.stderr)
            continue
        extra = merge_bindings(rows)
        for qid, rec in extra.items():
            target = out.setdefault(
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
            target["located"].update(rec["located"])
            target["iso"].update(rec["iso"])
        time.sleep(0.15)
    return out


def collect_known_qids(root: Path, rels: tuple[str, ...] | list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for rel in rels:
        path = root / rel
        if not path.is_file():
            continue
        _header, rows = read_csv(path)
        for row in rows:
            qid = qid_of_place(row)
            if qid and qid not in seen:
                seen.add(qid)
                out.append(qid)
    return out


def known_ids_queries(
    qids: list[str], batch_size: int = KNOWN_IDS_BATCH
) -> list[str]:
    if not qids:
        return []
    size = max(1, int(batch_size))
    out: list[str] = []
    for offset in range(0, len(qids), size):
        values = " ".join(f"wd:{qid}" for qid in qids[offset : offset + size])
        out.append(KNOWN_IDS_QUERY % values)
    return out


def fetch_known_ids(
    session: requests.Session,
    qids: list[str],
    batch_size: int = KNOWN_IDS_BATCH,
    timeout: int = 60,
) -> dict[str, dict[str, Any]]:
    queries = known_ids_queries(qids, batch_size)
    if not queries:
        return {}
    out: dict[str, dict[str, Any]] = {}
    total = len(queries)
    for index, query in enumerate(queries):
        if index == 0 or (index % 10 == 0):
            print(f"known-ids {index}/{total}", file=sys.stderr)
        rows = sparql_csv(session, query, timeout=timeout)
        extra = merge_bindings(rows, extra_scalars=("oktmo",))
        for qid, rec in extra.items():
            out.setdefault(qid, rec)
        time.sleep(0.15)
    return out


def mapped_known_fields(rec: dict[str, Any]) -> dict[str, str]:
    qid = str(rec.get("qid") or "")
    ru_raw = str(rec.get("ru") or "").strip()
    name_yo = ""
    if ru_raw and ru_raw != yo_to_e(ru_raw):
        name_yo = ru_raw
    oktmo = "".join(ch for ch in str(rec.get("oktmo") or "") if ch.isdigit())
    return {
        "id": f"wd:{qid}" if qid else "",
        "name_en": str(rec.get("en") or ""),
        "name_yo": name_yo,
        "lat": str(rec.get("lat") or ""),
        "lon": str(rec.get("lon") or ""),
        "wd": qid,
        "geonames": str(rec.get("gn") or ""),
        "oktmo": oktmo,
    }


def utc_today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())
