from __future__ import annotations

from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.harvest import merge_bindings
from scripts.seed_microtoponyms import (
    MICRO_SKIP_RELS,
    apply_harvest,
    harvest,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_microtoponym,
    p31_from_query,
    queries_for_p31,
    skip_ids,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "microtoponyms_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "microtoponyms-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _copy_csv(src: Path, dest: Path) -> None:
    header, rows = read_csv(src)
    write_csv(dest, header, rows)


def test_sparql_microtoponyms_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    for qid in (
        "Q1434274",
        "Q125505344",
        "Q1361400",
        "Q188869",
        "Q35509",
        "Q22698",
        "Q159",
    ):
        assert qid in text
    assert "Q4421" in text
    assert "Q2042028" in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_load_main_query_p31_parks_last() -> None:
    query = load_main_query(SPARQL)
    types = p31_from_query(query)
    assert types == [
        "Q1434274",
        "Q125505344",
        "Q1361400",
        "Q188869",
        "Q35509",
        "Q22698",
    ]
    split = queries_for_p31(query)
    assert [qid for qid, _typed in split] == types
    assert types[-1] == "Q22698"
    for qid, typed in split:
        assert f"VALUES ?type {{ wd:{qid} }}" in typed
        assert "wd:Q1434274 wd:Q125505344" not in typed


def test_micro_skip_rels_frozen_without_self() -> None:
    rels = {str(path).replace("\\", "/") for path in MICRO_SKIP_RELS}
    assert "data/curated/microtoponyms.csv" not in rels
    assert "data/curated/oronyms-major.csv" in rels
    assert "data/curated/municipalities.csv" in rels
    assert "data/curated/cities-major.csv" in rels


def test_map_microtoponym_yo_and_stable_id() -> None:
    rec = {
        "qid": "Q90002004",
        "ru": "Зелёное поле",
        "en": "Zelyonoye Field",
        "lat": "",
        "lon": "",
        "gn": "",
    }
    row = map_microtoponym(rec, ("iso:RU-MOS", "RU-MOS"), "2026-09-14")
    assert row["id"] == "wd:Q90002004"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "microtoponym"
    assert row["name_ru"] == "Зеленое поле"
    assert row["name_yo"] == "Зелёное поле"
    assert row["parent_id"] == "iso:RU-MOS"
    assert row["source_id"] == "wikidata"


def test_apply_harvest_city_parent_keeps_notes_skips_overlap() -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(rows)
    index = load_parent_index(ROOT)
    _header, existing = read_csv(ROOT / "data/curated/microtoponyms.csv")
    skip_map = skip_ids(ROOT)
    places, decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=[],
        today="2026-09-14",
        skip_map=skip_map,
    )
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q90002001"]["parent_id"] == "wd:Q649"
    assert by_id["wd:Q90002002"]["type_id"] == "microtoponym"
    assert by_id["wd:Q90002004"]["name_ru"] == "Зеленое поле"
    assert "wd:Q90002003" not in by_id
    assert counts.skipped_parent >= 1
    assert "wd:Q43105" not in by_id
    assert counts.skipped_overlap >= 1
    kapova = by_id["wd:Q1643788"]
    assert "Шульган-Таш" in kapova["notes"]
    assert by_id["local:micro:sinie-kamni"]["source_id"] == "gkgn-opendata"
    stubs = [row for row in decls if row["id"] == "wd:Q90002001"]
    assert len(stubs) == 1
    assert stubs[0]["type_code"] == "microtoponym"
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["source"] == "wikidata"


def test_cli_from_json_writes_tmp(tmp_path: Path, capsys) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/cities-major.csv", curated / "cities-major.csv")
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(
        curated / "municipalities.csv",
        PLACES_HEADER,
        [_place(id="wd:Q9", wd="Q9", type_id="municipality", name_ru="stub")],
    )
    write_csv(
        curated / "oronyms-major.csv",
        PLACES_HEADER,
        [_place(id="wd:Q43105", wd="Q43105", name_ru="Эльбрус", type_id="oronym")],
    )
    _header, micro = read_csv(ROOT / "data/curated/microtoponyms.csv")
    write_csv(curated / "microtoponyms.csv", _header, micro)
    write_csv(decl / "microtoponyms.csv", DECLENSIONS_HEADER, [])
    sparql_text = SPARQL.read_text(encoding="utf-8")
    (raw / "microtoponyms-ru.sparql").write_text(sparql_text, encoding="utf-8")
    code = main(
        [
            "--root",
            str(tmp_path),
            "--from-json",
            str(FIXTURE),
            "--no-hop",
            "--today",
            "2026-09-14",
        ]
    )
    assert code == 0
    out = capsys.readouterr()
    assert "ok\t" in out.out
    assert "skipped_other=" in out.out
    assert "skipped_overlap=" in out.out
    assert "bytes_places=" in out.out
    assert "skip overlap wd:Q43105 table=oronyms-major" in out.err
    _header, rows = read_csv(curated / "microtoponyms.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["wd:Q90002001"]["parent_id"] == "wd:Q649"
    assert "wd:Q43105" not in by_id
    assert "wd:Q90002003" not in by_id
    assert "local:micro:sinie-kamni" in by_id
    assert "Шульган-Таш" in by_id["wd:Q1643788"]["notes"]
    assert len(read_csv(ROOT / "data/curated/microtoponyms.csv")[1]) >= 100


def test_harvest_from_json_no_network() -> None:
    places, _decls, counts, _ph, _dh = harvest(
        root=ROOT,
        today="2026-09-14",
        from_json=FIXTURE,
        from_csv=None,
        hop=False,
        hop_batch=80,
        session=None,
    )
    assert counts.incoming >= 5
    assert any(row["id"] == "local:micro:sinie-kamni" for row in places)
    assert any(row["id"] == "wd:Q1643788" for row in places)
    assert len(read_csv(ROOT / "data/curated/microtoponyms.csv")[1]) >= 100


def test_canon_microtoponyms_harvested() -> None:
    _header, rows = read_csv(ROOT / "data/curated/microtoponyms.csv")
    assert len(rows) >= 100
    assert any(row["id"] == "local:micro:sinie-kamni" for row in rows)
    assert any(row["id"] == "wd:Q1643788" for row in rows)
    assert all(row["type_id"] == "microtoponym" for row in rows)
