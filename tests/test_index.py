from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import scripts.index as index_mod
from scripts.lib.csvio import PLACES_HEADER, write_csv
from scripts.lib.places import (
    AGENCIES_SCHEMA,
    INDEX_RELPATHS,
    PLACE_RELPATHS,
    PLACES_SCHEMA,
    load_index_relpaths,
    load_place_relpaths,
)

ROOT = Path(__file__).resolve().parents[1]
DATAPACKAGE = ROOT / "datapackage.json"
MAX_BYTES = 10 * 1024 * 1024


def _expected_relpaths() -> tuple[list[str], list[str]]:
    payload = json.loads(DATAPACKAGE.read_text(encoding="utf-8"))
    places: list[str] = []
    agencies: list[str] = []
    for res in payload.get("resources") or []:
        schema = res.get("schema")
        path = res.get("path") or ""
        if schema == PLACES_SCHEMA:
            places.append(path)
        elif schema == AGENCIES_SCHEMA:
            agencies.append(path)
    return places, places + agencies


def test_place_relpaths_exclude_agencies() -> None:
    places, index = _expected_relpaths()
    assert PLACE_RELPATHS == places
    assert INDEX_RELPATHS == index
    assert "data/curated/municipalities.csv" in PLACE_RELPATHS
    assert "data/curated/dromonyms.csv" in PLACE_RELPATHS
    assert "data/curated/agencies-foiv.csv" not in PLACE_RELPATHS
    assert "data/curated/agencies-other.csv" not in PLACE_RELPATHS
    assert "data/curated/types.csv" not in PLACE_RELPATHS
    assert "data/curated/types.csv" not in INDEX_RELPATHS
    assert not any(path.startswith("data/declensions/") for path in PLACE_RELPATHS)
    assert not any(path.startswith("data/declensions/") for path in INDEX_RELPATHS)
    assert "data/curated/agencies-foiv.csv" in INDEX_RELPATHS
    assert "data/curated/agencies-other.csv" in INDEX_RELPATHS


def _write_tmp_package(tmp_path: Path) -> Path:
    curated = tmp_path / "data" / "curated"
    curated.mkdir(parents=True)
    extra = "data/curated/extra-places.csv"
    agencies = "data/curated/agencies-foiv.csv"
    payload = {
        "resources": [
            {"name": "extra-places", "path": extra, "schema": PLACES_SCHEMA},
            {
                "name": "types",
                "path": "data/curated/types.csv",
                "schema": "schema/table/types.schema.json",
            },
            {
                "name": "declensions-extra",
                "path": "data/declensions/extra-places.csv",
                "schema": "schema/table/declensions.schema.json",
            },
            {"name": "agencies-foiv", "path": agencies, "schema": AGENCIES_SCHEMA},
        ]
    }
    (tmp_path / "datapackage.json").write_text(json.dumps(payload), encoding="utf-8")
    write_csv(
        tmp_path / extra,
        PLACES_HEADER,
        [{"id": "extra:1", "name_ru": "Экстра", "type_id": "city", "status": "active"}],
    )
    write_csv(
        tmp_path / agencies,
        PLACES_HEADER,
        [{"id": "foiv:extra", "name_ru": "ЭкстраФОИВ", "type_id": "foiv", "status": "active"}],
    )
    return tmp_path


def test_load_relpaths_reads_tmp_datapackage(tmp_path: Path) -> None:
    root = _write_tmp_package(tmp_path)
    assert load_place_relpaths(root) == ["data/curated/extra-places.csv"]
    assert load_index_relpaths(root) == [
        "data/curated/extra-places.csv",
        "data/curated/agencies-foiv.csv",
    ]
    ids = {row["id"] for row in index_mod.load_records(root)}
    assert ids == {"extra:1", "foiv:extra"}


def test_list_resource_path_raises(tmp_path: Path) -> None:
    payload = {
        "resources": [
            {
                "path": ["data/curated/a.csv", "data/curated/b.csv"],
                "schema": PLACES_SCHEMA,
            }
        ]
    }
    (tmp_path / "datapackage.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="string"):
        load_place_relpaths(tmp_path)


def _build(tmp_path: Path) -> Path:
    db_path = tmp_path / "registry.db"
    stats = index_mod.rebuild_index(ROOT, db_path)
    assert stats["records"] > 0
    assert db_path.is_file()
    return db_path


def test_index_rebuilds_to_temp_db(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    last = db_path.parent / "LAST_INDEX"
    assert last.is_file()
    line = last.read_text(encoding="utf-8").strip()
    stamp, count = line.split()
    assert "T" in stamp and stamp.endswith("Z")
    assert int(count) > 0
    assert db_path.stat().st_size < MAX_BYTES


def test_fts_volga_hits_hydronym(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    ids = index_mod.fts_match(db_path, "Волга")
    assert "wd:Q626" in ids
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT type_id, name_ru, table_name FROM records WHERE id = ?",
            ("wd:Q626",),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    type_id, name_ru, table_name = row
    assert name_ru == "Волга"
    assert type_id in {"potamonym", "hydronym", "limnonym"}
    assert table_name == "hydronyms-major"


def test_fts_mvd_hits_foiv(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    ids = index_mod.fts_match(db_path, "МВД")
    assert "foiv:mvd" in ids


def test_records_store_coords_outside_fts(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    rec = index_mod.get_record(db_path, "wd:Q649")
    assert rec is not None
    assert isinstance(rec["lat"], float)
    assert isinstance(rec["lon"], float)
    assert 55.0 < rec["lat"] < 56.0
    assert rec["oktmo"] == "45000000"
    assert rec["fias"] == ""
    conn = sqlite3.connect(db_path)
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(records)").fetchall()]
        fts_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'records_fts'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert "lat" in cols and "lon" in cols and "fias" in cols and "oktmo" in cols
    assert "lat" not in fts_sql
    assert "lon" not in fts_sql
    assert "oktmo" not in fts_sql
    assert "fias" not in fts_sql
    assert "name_ru" in fts_sql
    assert "lemma" in fts_sql
    assert "lemma" not in cols


def test_fts_yo_hits_orel_and_black_sea(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    assert "wd:Q3118" in index_mod.fts_match(db_path, "Орёл")
    assert "wd:Q3118" in index_mod.fts_match(db_path, "Орел")
    assert "wd:Q166" in index_mod.fts_match(db_path, "Чёрное")
    rec = index_mod.get_record(db_path, "wd:Q3118")
    assert rec is not None
    assert rec["name_ru"] == "Орел"
    assert rec["name_yo"] == "Орёл"


def test_fts_tverskaya_hits_hodonym(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    ids = index_mod.fts_match(db_path, "Тверская")
    assert "wd:Q1644209" in ids
    assert "wd:Q1644209" in index_mod.fts_match(db_path, "Тверской")
    rec = index_mod.get_record(db_path, "wd:Q1644209")
    assert rec is not None
    assert rec["name_ru"] == "Тверская улица"
    assert "lemma" not in rec
    assert "wd:Q649" in index_mod.fts_match(db_path, "Москвы")
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT type_id, name_ru, table_name FROM records WHERE id = ?",
            ("wd:Q1644209",),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    type_id, name_ru, table_name = row
    assert name_ru == "Тверская улица"
    assert type_id == "hodonym"
    assert table_name == "hodonyms"


def test_fts_expanded_seeds_street_and_municipality(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    assert "wd:Q269373" in index_mod.fts_match(db_path, "Арбат")
    rec = index_mod.get_record(db_path, "wd:Q269373")
    assert rec is not None
    assert rec["name_ru"] == "Арбат"
    assert rec["table_name"] == "hodonyms"
    assert rec["type_id"] == "hodonym"
    assert "wd:Q15190285" in index_mod.fts_match(db_path, "Уфа")
    mun = index_mod.get_record(db_path, "wd:Q15190285")
    assert mun is not None
    assert mun["table_name"] == "municipalities"
    assert mun["type_id"] == "municipality"
    assert "wd:Q1643788" in index_mod.fts_match(db_path, "Капова")
    cave = index_mod.get_record(db_path, "wd:Q1643788")
    assert cave is not None
    assert cave["name_ru"] == "Капова пещера"
    assert cave["table_name"] == "microtoponyms"


def test_fts_dva_seeds(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    assert "wd:Q41116" in index_mod.fts_match(db_path, "Красная")
    square = index_mod.get_record(db_path, "wd:Q41116")
    assert square is not None
    assert square["name_ru"] == "Красная площадь"
    assert square["type_id"] == "agoronym"
    assert square["table_name"] == "agoronyms"
    assert "wd:Q894049" in index_mod.fts_match(db_path, "Бородино")
    village = index_mod.get_record(db_path, "wd:Q894049")
    assert village is not None
    assert village["type_id"] == "village"
    assert village["table_name"] == "villages"
    assert "wd:Q58767" in index_mod.fts_match(db_path, "Транссиб")
    rail = index_mod.get_record(db_path, "wd:Q58767")
    assert rail is not None
    assert rail["type_id"] == "dromonym"
    assert rail["table_name"] == "dromonyms"
    assert rail["abbr"] == "Транссиб"


def test_sync_meta_from_catalog(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    conn = sqlite3.connect(db_path)
    try:
        sources = {row[0] for row in conn.execute("SELECT source_id FROM sync_meta")}
    finally:
        conn.close()
    assert "geonames-ru" in sources
    assert "ukase-326" in sources
    assert "wikidata" in sources


def test_fts_search_returns_records(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    hits = index_mod.fts_search(db_path, '"Волга"', limit=1)
    assert hits
    assert hits[0]["id"] == "wd:Q626"
    assert hits[0]["table_name"] == "hydronyms-major"


def test_cli_out_temp_db(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "cli.db"
    code = index_mod.main(["--out", str(db_path)])
    captured = capsys.readouterr()
    assert code == 0
    assert db_path.is_file()
    assert "ok records=" in captured.out
    assert "foiv:mvd" in index_mod.fts_match(db_path, "МВД")
