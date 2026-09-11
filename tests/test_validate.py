from __future__ import annotations

import json
import shutil
from pathlib import Path

import scripts.validate as validate_mod

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
