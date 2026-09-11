from __future__ import annotations

import sqlite3
from pathlib import Path

import scripts.index as index_mod
import scripts.sync as sync_mod
from scripts.lib.places import INDEX_RELPATHS, PLACE_RELPATHS

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024


def test_place_relpaths_exclude_agencies() -> None:
    assert PLACE_RELPATHS == [
        "data/curated/federal-districts.csv",
        "data/curated/regions.csv",
        "data/curated/cities-major.csv",
        "data/curated/hydronyms-major.csv",
        "data/curated/oronyms-major.csv",
        "data/curated/municipalities.csv",
        "data/curated/hodonyms.csv",
        "data/curated/microtoponyms.csv",
    ]
    assert INDEX_RELPATHS == PLACE_RELPATHS + [
        "data/curated/agencies-foiv.csv",
        "data/curated/agencies-other.csv",
    ]
    assert index_mod.INDEX_RELPATHS is INDEX_RELPATHS
    assert sync_mod.PLACE_RELPATHS is PLACE_RELPATHS
    assert "data/curated/agencies-foiv.csv" not in sync_mod.PLACE_RELPATHS


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


def test_fts_tverskaya_hits_hodonym(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    ids = index_mod.fts_match(db_path, "Тверская")
    assert "wd:Q1644209" in ids
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
