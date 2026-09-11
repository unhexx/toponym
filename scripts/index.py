#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.catalog import load_catalog  # noqa: E402
from scripts.lib.csvio import read_csv  # noqa: E402
from scripts.lib.detectors import utcnow  # noqa: E402

ROOT = _ROOT
DEFAULT_OUT = ROOT / "knowledge" / "registry.db"

PLACE_RELPATHS = [
    "data/curated/federal-districts.csv",
    "data/curated/regions.csv",
    "data/curated/cities-major.csv",
    "data/curated/hydronyms-major.csv",
    "data/curated/oronyms-major.csv",
    "data/curated/municipalities.csv",
    "data/curated/hodonyms.csv",
    "data/curated/microtoponyms.csv",
    "data/curated/agencies-foiv.csv",
    "data/curated/agencies-other.csv",
]

RECORD_FIELDS = (
    "id",
    "table_name",
    "type_id",
    "name_ru",
    "name_yo",
    "name_en",
    "abbr",
    "parent_id",
    "admin1",
    "wd",
    "geonames",
    "iso",
    "status",
    "source_id",
)

SCHEMA_SQL = """
CREATE TABLE records (
  id TEXT PRIMARY KEY,
  table_name TEXT NOT NULL,
  type_id TEXT,
  name_ru TEXT,
  name_yo TEXT,
  name_en TEXT,
  abbr TEXT,
  parent_id TEXT,
  admin1 TEXT,
  wd TEXT,
  geonames TEXT,
  iso TEXT,
  status TEXT,
  source_id TEXT
);
CREATE VIRTUAL TABLE records_fts USING fts5(
  name_ru, name_yo, name_en, abbr, wd,
  tokenize='unicode61'
);
CREATE TABLE sync_meta (
  source_id TEXT PRIMARY KEY,
  checked_at TEXT,
  cursor TEXT,
  hash TEXT
);
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Пересобрать SQLite FTS5 из канонических CSV")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="путь к registry.db (по умолчанию knowledge/registry.db)",
    )
    return parser.parse_args(argv)


def _unlink_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    extras = (path, *(Path(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal")))
    for candidate in extras:
        if candidate.is_file():
            candidate.unlink()


def _cell(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def load_records(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for rel in PLACE_RELPATHS:
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(f"нет таблицы {rel}")
        _header, rows = read_csv(path)
        table_name = path.stem
        for row in rows:
            rid = _cell(row, "id")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            records.append(
                {
                    "id": rid,
                    "table_name": table_name,
                    "type_id": _cell(row, "type_id"),
                    "name_ru": _cell(row, "name_ru"),
                    "name_yo": _cell(row, "name_yo"),
                    "name_en": _cell(row, "name_en"),
                    "abbr": _cell(row, "abbr"),
                    "parent_id": _cell(row, "parent_id"),
                    "admin1": _cell(row, "admin1"),
                    "wd": _cell(row, "wd"),
                    "geonames": _cell(row, "geonames"),
                    "iso": _cell(row, "iso"),
                    "status": _cell(row, "status"),
                    "source_id": _cell(row, "source_id"),
                }
            )
    return records


def load_sync_meta(root: Path) -> list[dict[str, str]]:
    catalog = load_catalog(root / "data" / "sources" / "catalog.yaml")
    rows: list[dict[str, str]] = []
    for source in catalog.get("sources") or []:
        sid = source.get("id") or ""
        if not sid:
            continue
        rows.append(
            {
                "source_id": sid,
                "checked_at": str(source.get("checked_at") or ""),
                "cursor": str(source.get("cursor") or ""),
                "hash": str(source.get("hash") or ""),
            }
        )
    return rows


def write_last_index(db_path: Path, n_records: int, stamp: str | None = None) -> Path:
    stamp = stamp or utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    path = db_path.parent / "LAST_INDEX"
    path.write_text(f"{stamp} {n_records}\n", encoding="utf-8")
    return path


def rebuild_index(root: Path, out_path: Path) -> dict[str, int]:
    records = load_records(root)
    meta = load_sync_meta(root)
    _unlink_db(out_path)
    conn = sqlite3.connect(out_path)
    try:
        conn.executescript(SCHEMA_SQL)
        placeholders = ",".join("?" for _ in RECORD_FIELDS)
        insert_sql = f"INSERT INTO records ({','.join(RECORD_FIELDS)}) VALUES ({placeholders})"
        fts_sql = (
            "INSERT INTO records_fts(rowid, name_ru, name_yo, name_en, abbr, wd) "
            "VALUES (?,?,?,?,?,?)"
        )
        for row in records:
            cur = conn.execute(insert_sql, [row[key] for key in RECORD_FIELDS])
            conn.execute(
                fts_sql,
                (
                    cur.lastrowid,
                    row["name_ru"],
                    row["name_yo"],
                    row["name_en"],
                    row["abbr"],
                    row["wd"],
                ),
            )
        conn.executemany(
            "INSERT INTO sync_meta (source_id, checked_at, cursor, hash) VALUES (?,?,?,?)",
            [(m["source_id"], m["checked_at"], m["cursor"], m["hash"]) for m in meta],
        )
        conn.commit()
    finally:
        conn.close()
    write_last_index(out_path, len(records))
    return {"records": len(records), "sources": len(meta)}


def fts_match(db_path: Path, query: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT r.id FROM records_fts f
            JOIN records r ON r.rowid = f.rowid
            WHERE records_fts MATCH ?
            """,
            (query,),
        ).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


def _row_to_record(row: tuple[object, ...]) -> dict[str, str]:
    return {
        key: "" if value is None else str(value)
        for key, value in zip(RECORD_FIELDS, row, strict=True)
    }


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def get_record(db_path: Path, record_id: str) -> dict[str, str] | None:
    conn = _connect_ro(db_path)
    try:
        row = conn.execute(
            f"SELECT {','.join(RECORD_FIELDS)} FROM records WHERE id = ?",
            (record_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _row_to_record(row)


def fts_search(
    db_path: Path,
    query: str,
    *,
    limit: int = 20,
    status: str | None = None,
    table_name: str | None = None,
) -> list[dict[str, str]]:
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            f"""
            SELECT {", ".join("r." + field for field in RECORD_FIELDS)}
            FROM records_fts AS f
            JOIN records AS r ON r.rowid = f.rowid
            WHERE records_fts MATCH ?
              AND (? IS NULL OR r.status = ?)
              AND (? IS NULL OR r.table_name = ?)
            LIMIT ?
            """,
            (query, status, status, table_name, table_name, limit),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_record(row) for row in rows]


def index_counts(db_path: Path) -> dict[str, int]:
    conn = _connect_ro(db_path)
    try:
        records = conn.execute("SELECT COUNT(*) FROM records").fetchone()
        sources = conn.execute("SELECT COUNT(*) FROM sync_meta").fetchone()
    finally:
        conn.close()
    return {
        "records": int(records[0]) if records else 0,
        "sources": int(sources[0]) if sources else 0,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    try:
        stats = rebuild_index(ROOT, out_path)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"ok records={stats['records']} sources={stats['sources']} db={out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
