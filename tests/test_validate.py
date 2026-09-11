from __future__ import annotations

import json
import shutil
from pathlib import Path

import scripts.validate as validate_mod
from scripts.lib.invariants import (
    FROZEN_TAXONOMY,
    SHAREALIKE_SOURCE_IDS,
    check_frozen_taxonomy,
    check_gn_id,
    check_gold_auto,
    check_name_yo,
    check_sharealike,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_validate_repo_ok(capsys) -> None:
    code = validate_mod.main(["--json", "--datapackage", str(ROOT / "datapackage.json")])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0, payload
    assert payload["ok"] is True
    assert payload["error_count"] == 0


def test_broken_csv_fails_in_tmp_datapackage(tmp_path: Path, capsys) -> None:
    dest = tmp_path / "pkg"
    dest.mkdir()
    shutil.copy(ROOT / "datapackage.json", dest / "datapackage.json")
    shutil.copytree(ROOT / "schema", dest / "schema")
    shutil.copytree(ROOT / "data", dest / "data")
    broken = (FIXTURES / "broken.csv").read_bytes()
    assert b"\r" in broken
    (dest / "data/curated/regions.csv").write_bytes(broken)
    code = validate_mod.main(["--json", "--datapackage", str(dest / "datapackage.json")])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1, payload
    checks = {row["check"] for row in payload["errors"]}
    assert "toropum" in checks or "yo" in checks or "unique" in checks or "crlf" in checks
    joined = " ".join(row["message"] for row in payload["errors"]).lower()
    assert "торопум" in joined or "ё" in joined or "повтор" in joined or "cr" in joined


def test_missing_datapackage_exit_2(tmp_path: Path, capsys) -> None:
    code = validate_mod.main(["--datapackage", str(tmp_path / "nope.json")])
    assert code == 2
    err = capsys.readouterr()
    assert "нет" in (err.err + err.out).lower() or "datapackage" in (err.err + err.out).lower()


def test_empty_lat_lon_accepted_on_seeds() -> None:
    code, errors = validate_mod.validate_tree(ROOT / "datapackage.json", root=ROOT)
    assert code == 0
    assert errors == []


def test_hflabs_source_id_fails_validate(tmp_path: Path) -> None:
    dest = tmp_path / "pkg"
    dest.mkdir()
    shutil.copy(ROOT / "datapackage.json", dest / "datapackage.json")
    shutil.copytree(ROOT / "schema", dest / "schema")
    shutil.copytree(ROOT / "data", dest / "data")
    path = dest / "data/curated/regions.csv"
    text = path.read_text(encoding="utf-8")
    assert ",wikidata," in text
    path.write_text(text.replace(",wikidata,", ",hflabs-region,", 1), encoding="utf-8")
    code, errors = validate_mod.validate_tree(dest / "datapackage.json", root=dest)
    assert code == 1
    assert any(row["check"] == "sharealike" for row in errors)


def test_renamed_taxonomy_root_fails_validate(tmp_path: Path) -> None:
    dest = tmp_path / "pkg"
    dest.mkdir()
    shutil.copy(ROOT / "datapackage.json", dest / "datapackage.json")
    shutil.copytree(ROOT / "schema", dest / "schema")
    shutil.copytree(ROOT / "data", dest / "data")
    path = dest / "data/curated/types.csv"
    text = path.read_text(encoding="utf-8")
    assert "toponym,root," in text
    path.write_text(text.replace("toponym,root,", "toponym,primary,", 1), encoding="utf-8")
    code, errors = validate_mod.validate_tree(dest / "datapackage.json", root=dest)
    assert code == 1
    assert any(row["check"] == "taxonomy" for row in errors)


def test_duplicate_declension_id_lemma_fails(tmp_path: Path) -> None:
    dest = tmp_path / "pkg"
    dest.mkdir()
    shutil.copy(ROOT / "datapackage.json", dest / "datapackage.json")
    shutil.copytree(ROOT / "schema", dest / "schema")
    shutil.copytree(ROOT / "data", dest / "data")
    path = dest / "data/declensions/agencies.csv"
    text = path.read_text(encoding="utf-8")
    first = next(line for line in text.splitlines() if line.startswith("foiv:mvd,"))
    path.write_text(text + first + "\n", encoding="utf-8")
    code, errors = validate_mod.validate_tree(dest / "datapackage.json", root=dest)
    assert code == 1
    assert any(row["check"] == "unique" and "foiv:mvd" in row["message"] for row in errors)


def test_gold_pymorphy_fails_validate(tmp_path: Path) -> None:
    dest = tmp_path / "pkg"
    dest.mkdir()
    shutil.copy(ROOT / "datapackage.json", dest / "datapackage.json")
    shutil.copytree(ROOT / "schema", dest / "schema")
    shutil.copytree(ROOT / "data", dest / "data")
    path = dest / "data/declensions/cities-major.csv"
    text = path.read_text(encoding="utf-8")
    assert ",gold,manual" in text
    path.write_text(text.replace(",gold,manual", ",gold,pymorphy3", 1), encoding="utf-8")
    code, errors = validate_mod.validate_tree(dest / "datapackage.json", root=dest)
    assert code == 1
    assert any(row["check"] == "gold_auto" for row in errors)


def test_gn_place_id_fails_validate(tmp_path: Path) -> None:
    dest = tmp_path / "pkg"
    dest.mkdir()
    shutil.copy(ROOT / "datapackage.json", dest / "datapackage.json")
    shutil.copytree(ROOT / "schema", dest / "schema")
    shutil.copytree(ROOT / "data", dest / "data")
    path = dest / "data/curated/hydronyms-major.csv"
    text = path.read_text(encoding="utf-8")
    assert "wd:Q626," in text
    path.write_text(text.replace("wd:Q626,", "gn:472776,", 1), encoding="utf-8")
    code, errors = validate_mod.validate_tree(dest / "datapackage.json", root=dest)
    assert code == 1
    assert any(row["check"] == "gn_id" for row in errors)


def test_check_gn_id_rejects_prefix() -> None:
    errors: list[dict] = []
    check_gn_id("gn:472776", "hydronyms-major", errors)
    assert errors[0]["check"] == "gn_id"
    assert errors[0]["resource"] == "hydronyms-major"
    ok: list[dict] = []
    check_gn_id("wd:Q626", "hydronyms-major", ok)
    assert ok == []


def test_check_sharealike_rejects_hflabs() -> None:
    assert "hflabs-region" in SHAREALIKE_SOURCE_IDS
    errors: list[dict] = []
    check_sharealike({"id": "wd:Q1", "source_id": "hflabs-region"}, "regions", errors)
    assert errors[0]["check"] == "sharealike"
    ok: list[dict] = []
    check_sharealike({"id": "wd:Q1", "source_id": "wikidata"}, "regions", ok)
    assert ok == []


def test_check_gold_auto_rejects_pymorphy() -> None:
    errors: list[dict] = []
    check_gold_auto(
        {"id": "wd:Q649", "review": "gold", "source": "pymorphy3"},
        "cities-major",
        errors,
    )
    assert errors[0]["check"] == "gold_auto"
    ok: list[dict] = []
    check_gold_auto(
        {"id": "wd:Q649", "review": "gold", "source": "manual"},
        "cities-major",
        ok,
    )
    assert ok == []
    skipped: list[dict] = []
    check_gold_auto(
        {"id": "wd:Q649", "review": "needs_review", "source": "pymorphy3"},
        "cities-major",
        skipped,
    )
    assert skipped == []


def test_check_name_yo_rejects_mismatch() -> None:
    ok: list[dict] = []
    check_name_yo(
        {"id": "wd:Q3118", "name_ru": "Орел", "name_yo": "Орёл"},
        "cities-major",
        ok,
    )
    assert ok == []
    empty: list[dict] = []
    check_name_yo(
        {"id": "wd:Q649", "name_ru": "Москва", "name_yo": ""},
        "cities-major",
        empty,
    )
    assert empty == []
    errors: list[dict] = []
    check_name_yo(
        {"id": "wd:Q3118", "name_ru": "Орёл", "name_yo": "Орёл"},
        "cities-major",
        errors,
    )
    assert any(row["check"] == "yo" and "name_ru" in row["message"] for row in errors)
    drift: list[dict] = []
    check_name_yo(
        {"id": "wd:Q3118", "name_ru": "Орел", "name_yo": "Орёл-град"},
        "cities-major",
        drift,
    )
    assert any(row["check"] == "yo" and "нормализация" in row["message"] for row in drift)
    no_yo: list[dict] = []
    check_name_yo(
        {"id": "wd:Q3118", "name_ru": "Орел", "name_yo": "Орел"},
        "cities-major",
        no_yo,
    )
    assert any(row["check"] == "yo" and "без ё" in row["message"] for row in no_yo)


def test_name_yo_mismatch_fails_validate(tmp_path: Path) -> None:
    dest = tmp_path / "pkg"
    dest.mkdir()
    shutil.copy(ROOT / "datapackage.json", dest / "datapackage.json")
    shutil.copytree(ROOT / "schema", dest / "schema")
    shutil.copytree(ROOT / "data", dest / "data")
    path = dest / "data/curated/hydronyms-major.csv"
    text = path.read_text(encoding="utf-8")
    assert "Черное море,Чёрное море," in text
    path.write_text(
        text.replace("Черное море,Чёрное море,", "Черное море,Черное море,", 1),
        encoding="utf-8",
    )
    code, errors = validate_mod.validate_tree(dest / "datapackage.json", root=dest)
    assert code == 1
    assert any(row["check"] == "yo" and "wd:Q166" in row["message"] for row in errors)


def test_check_frozen_taxonomy_rejects_renamed_root() -> None:
    rows = [
        {"id": tid, "level": spec["level"], "parent_id": spec["parent_id"]}
        for tid, spec in FROZEN_TAXONOMY.items()
    ]
    ok: list[dict] = []
    check_frozen_taxonomy(rows, ok)
    assert ok == []
    rows[0]["level"] = "primary"
    errors: list[dict] = []
    check_frozen_taxonomy(rows, errors)
    assert any(row["check"] == "taxonomy" for row in errors)
