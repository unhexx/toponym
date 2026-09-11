from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.declensions_queue as queue_cli
from scripts.lib.csvio import read_csv, write_csv
from scripts.lib.declensions import (
    DECLENSIONS_HEADER,
    GOLD_RELPATHS,
    QUEUE_RELPATH,
    DeclensionError,
    append_queue,
    is_auto_source,
    load_lemma_aliases,
    prepare_queue_row,
)
from scripts.lib.upsert import upsert_rows

ROOT = Path(__file__).resolve().parents[1]
DATAPACKAGE = ROOT / "datapackage.json"


def test_queue_csv_exists_and_is_not_a_resource() -> None:
    path = ROOT / QUEUE_RELPATH
    assert path.is_file()
    raw = path.read_bytes()
    assert b"\r" not in raw
    header, rows = read_csv(path)
    assert header == DECLENSIONS_HEADER
    assert all(row.get("review") != "gold" for row in rows)
    pkg = json.loads(DATAPACKAGE.read_text(encoding="utf-8"))
    paths = {resource["path"] for resource in pkg["resources"]}
    assert "data/declensions/queue.csv" not in paths


def test_lemma_aliases_skip_queue_and_join_cases(tmp_path: Path) -> None:
    aliases = load_lemma_aliases(ROOT)
    tverskaya = aliases["wd:Q1644209"]
    assert "Тверская улица" in tverskaya
    assert "Тверской" in tverskaya
    assert "Москвы" in aliases["wd:Q649"]
    dest = tmp_path / "data/declensions"
    dest.mkdir(parents=True)
    write_csv(
        dest / "hodonyms.csv",
        DECLENSIONS_HEADER,
        [
            {
                **{key: "" for key in DECLENSIONS_HEADER},
                "id": "wd:Q1644209",
                "lemma": "Тверская улица",
                "gen": "Тверской улицы",
                "review": "needs_review",
                "source": "manual",
            }
        ],
    )
    write_csv(
        tmp_path / QUEUE_RELPATH,
        DECLENSIONS_HEADER,
        [
            {
                **{key: "" for key in DECLENSIONS_HEADER},
                "id": "local:queue-only",
                "lemma": "Очередьалиас",
                "review": "needs_review",
                "source": "auto",
            }
        ],
    )
    isolated = load_lemma_aliases(tmp_path)
    assert "local:queue-only" not in isolated
    assert "Очередьалиас" not in isolated.get("wd:Q1644209", "")
    assert "Тверской" in isolated["wd:Q1644209"]


def test_gold_tables_have_no_pymorphy_natasha() -> None:
    for rel in GOLD_RELPATHS:
        _header, rows = read_csv(ROOT / rel)
        for row in rows:
            if row.get("review") == "gold":
                assert not is_auto_source(row.get("source") or ""), (rel, row["id"])


def test_pyproject_has_no_morphology_deps() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8").casefold()
    for name in ("pymorphy", "natasha", "pyphrasy"):
        assert name not in text, name


def test_prepare_queue_rejects_gold() -> None:
    with pytest.raises(DeclensionError, match="gold"):
        prepare_queue_row(
            {
                "id": "wd:Q649",
                "type_code": "city",
                "lemma": "Москва",
                "review": "gold",
                "source": "pymorphy3",
            }
        )


def test_append_queue_writes_needs_review_not_gold_tables(tmp_path: Path) -> None:
    gold = tmp_path / "data/declensions/cities-major.csv"
    gold_row = {key: "" for key in DECLENSIONS_HEADER}
    gold_row.update(
        {
            "id": "wd:Q649",
            "type_code": "city",
            "lemma": "Москва",
            "review": "gold",
            "source": "manual",
        }
    )
    write_csv(gold, DECLENSIONS_HEADER, [gold_row])
    before = gold.read_bytes()
    queue = tmp_path / QUEUE_RELPATH
    write_csv(queue, DECLENSIONS_HEADER, [])
    path, added = append_queue(
        tmp_path,
        [
            {
                "id": "wd:Q42",
                "type_code": "city",
                "lemma": "Примерск",
                "review": "needs_review",
                "source": "pymorphy3",
                "gender": "m",
                "paradigm": "noun_m2",
                "declinable": "always",
                "nom": "Примерск",
            }
        ],
        apply=True,
    )
    assert added == 1
    assert path == queue
    header, rows = read_csv(queue)
    assert header == DECLENSIONS_HEADER
    assert len(rows) == 1
    assert rows[0]["review"] == "needs_review"
    assert rows[0]["source"] == "pymorphy3"
    assert gold.read_bytes() == before


def test_append_queue_dry_run_does_not_write(tmp_path: Path) -> None:
    queue = tmp_path / QUEUE_RELPATH
    write_csv(queue, DECLENSIONS_HEADER, [])
    before = queue.read_bytes()
    _path, added = append_queue(
        tmp_path,
        [{"id": "wd:Q1", "lemma": "Тест", "review": "auto", "type_code": "city"}],
        apply=False,
    )
    assert added == 1
    assert queue.read_bytes() == before


def test_cli_appends_queue_and_leaves_gold(tmp_path: Path) -> None:
    gold = tmp_path / "data/declensions/cities-major.csv"
    gold.parent.mkdir(parents=True)
    gold_row = {key: "" for key in DECLENSIONS_HEADER}
    gold_row.update(
        {
            "id": "wd:Q649",
            "type_code": "city",
            "lemma": "Москва",
            "review": "gold",
            "source": "manual",
        }
    )
    write_csv(gold, DECLENSIONS_HEADER, [gold_row])
    write_csv(tmp_path / QUEUE_RELPATH, DECLENSIONS_HEADER, [])
    before_gold = gold.read_bytes()
    code = queue_cli.main(
        [
            "--root",
            str(tmp_path),
            "--id",
            "wd:Q42",
            "--lemma",
            "Примерск",
            "--type-code",
            "city",
        ]
    )
    assert code == 0
    header, rows = read_csv(tmp_path / QUEUE_RELPATH)
    assert header == DECLENSIONS_HEADER
    assert len(rows) == 1
    assert rows[0]["id"] == "wd:Q42"
    assert rows[0]["lemma"] == "Примерск"
    assert rows[0]["review"] == "needs_review"
    assert rows[0]["nom"] == "Примерск"
    assert gold.read_bytes() == before_gold
    regions = tmp_path / "data/declensions/regions.csv"
    agencies = tmp_path / "data/declensions/agencies.csv"
    assert not regions.exists()
    assert not agencies.exists()


def test_cli_rejects_gold_review(tmp_path: Path) -> None:
    write_csv(tmp_path / QUEUE_RELPATH, DECLENSIONS_HEADER, [])
    before = (tmp_path / QUEUE_RELPATH).read_bytes()
    code = queue_cli.main(
        [
            "--root",
            str(tmp_path),
            "--id",
            "wd:Q649",
            "--lemma",
            "Москва",
            "--review",
            "gold",
        ]
    )
    assert code == 2
    assert (tmp_path / QUEUE_RELPATH).read_bytes() == before


def test_cli_dry_run_does_not_write(tmp_path: Path) -> None:
    write_csv(tmp_path / QUEUE_RELPATH, DECLENSIONS_HEADER, [])
    before = (tmp_path / QUEUE_RELPATH).read_bytes()
    code = queue_cli.main(
        [
            "--root",
            str(tmp_path),
            "--id",
            "wd:Q1",
            "--lemma",
            "Тест",
            "--dry-run",
        ]
    )
    assert code == 0
    assert (tmp_path / QUEUE_RELPATH).read_bytes() == before


def test_upsert_still_skips_gold() -> None:
    existing = [
        {key: "" for key in DECLENSIONS_HEADER}
        | {"id": "wd:Q649", "lemma": "Москва", "review": "gold", "ins": "Москвой"}
    ]
    incoming = [
        {key: "" for key in DECLENSIONS_HEADER}
        | {"id": "wd:Q649", "lemma": "Москва", "review": "auto", "ins": "Москвой-авто"}
    ]
    rows, counts = upsert_rows(
        existing, incoming, header=DECLENSIONS_HEADER, gold_field="review", gold_value="gold"
    )
    assert rows[0]["ins"] == "Москвой"
    assert rows[0]["review"] == "gold"
    assert counts.skipped_gold == 1
    assert counts.updated == 0
