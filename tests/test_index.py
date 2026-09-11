from __future__ import annotations

import sqlite3
from pathlib import Path

import scripts.index as index_mod

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024


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
