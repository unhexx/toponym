from __future__ import annotations

from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.harvest import merge_bindings
from scripts.seed_dromonyms import (
    DRO_SKIP_RELS,
    apply_harvest,
    harvest,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_dromonym,
    p31_from_query,
    queries_for_p31,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "dromonyms_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "dromonyms-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _copy_csv(src: Path, dest: Path) -> None:
    header, rows = read_csv(src)
    write_csv(dest, header, rows)


def _transsib(**kwargs: str) -> dict[str, str]:
    row = _place(
        id="wd:Q58767",
        id_scheme="wikidata",
        type_id="dromonym",
        name_ru="Транссибирская магистраль",
        name_en="Trans-Siberian railway",
        abbr="Транссиб",
        wd="Q58767",
        status="active",
        source_id="wikidata",
        updated_at="2026-09-12",
        notes="пример types.csv; железная дорога, не ГАР",
    )
    row.update(kwargs)
    return row


def test_sparql_dromonyms_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    assert "Q34442" in text
    assert "Q728937" in text
    assert "Q159" in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    assert "FILTER(?type != wd:Q728937" in text
    assert "ru.wikipedia.org" in text
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_load_main_query_dromonym_p31_rail_last() -> None:
    query = load_main_query(SPARQL)
    types = p31_from_query(query)
    assert types == ["Q34442", "Q728937"]
    split = queries_for_p31(query)
    assert [qid for qid, _typed in split] == types
    assert types[-1] == "Q728937"
    for qid, typed in split:
        assert f"VALUES ?type {{ wd:{qid} }}" in typed
        assert "wd:Q34442 wd:Q728937" not in typed
        assert "FILTER(?type != wd:Q728937" in typed


def test_dro_skip_rels_frozen_without_self() -> None:
    rels = {str(path).replace("\\", "/") for path in DRO_SKIP_RELS}
    assert "data/curated/dromonyms.csv" not in rels
    assert "data/curated/hodonyms.csv" in rels
    assert "data/curated/agoronyms.csv" in rels
    assert "data/curated/cities-major.csv" in rels
    assert "data/curated/regions.csv" in rels


def test_map_dromonym_yo_and_stable_id() -> None:
    rec = {
        "qid": "Q90005003",
        "ru": "Зелёная железная дорога",
        "en": "Zelyonaya Railway",
        "lat": "",
        "lon": "",
        "gn": "",
    }
    row = map_dromonym(rec, ("iso:RU-MOS", "RU-MOS"), "2026-09-15")
    assert row["id"] == "wd:Q90005003"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "dromonym"
    assert row["name_ru"] == "Зеленая железная дорога"
    assert row["name_yo"] == "Зелёная железная дорога"
    assert row["parent_id"] == "iso:RU-MOS"
    assert row["source_id"] == "wikidata"


def test_apply_harvest_region_parent_keeps_notes_skips_overlap() -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(rows, extra_qid_sets=("p31",))
    index = load_parent_index(ROOT)
    existing = [_transsib()]
    skip_map = {"Q90005004": "hodonyms"}
    places, decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=[],
        today="2026-09-15",
        skip_map=skip_map,
    )
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q90005001"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q90005001"]["type_id"] == "dromonym"
    assert "wd:Q90005002" not in by_id
    assert counts.skipped_parent >= 1
    assert "wd:Q90005004" not in by_id
    assert counts.skipped_overlap >= 1
    transsib = by_id["wd:Q58767"]
    assert transsib["notes"].startswith("пример types.csv")
    assert transsib["abbr"] == "Транссиб"
    assert by_id["wd:Q90005003"]["type_id"] == "dromonym"
    assert by_id["wd:Q90005003"]["name_ru"] == "Зеленая железная дорога"
    stubs = [row for row in decls if row["id"] == "wd:Q90005001"]
    assert len(stubs) == 1
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["type_code"] == "dromonym"
    assert stubs[0]["source"] == "wikidata"
    assert all(row["review"] != "gold" for row in decls)


def test_cli_from_json_writes_tmp(tmp_path: Path, capsys) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    _copy_csv(ROOT / "data/curated/cities-major.csv", curated / "cities-major.csv")
    write_csv(
        curated / "hodonyms.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q90005004",
                wd="Q90005004",
                name_ru="Перекрытие с улицей",
                type_id="hodonym",
            )
        ],
    )
    write_csv(
        curated / "agoronyms.csv",
        PLACES_HEADER,
        [_place(id="wd:Q41116", wd="Q41116", name_ru="Красная площадь")],
    )
    write_csv(curated / "dromonyms.csv", PLACES_HEADER, [_transsib()])
    write_csv(decl / "dromonyms.csv", DECLENSIONS_HEADER, [])
    (raw / "dromonyms-ru.sparql").write_text(SPARQL.read_text(encoding="utf-8"), encoding="utf-8")
    code = main(
        [
            "--root",
            str(tmp_path),
            "--from-json",
            str(FIXTURE),
            "--no-hop",
            "--today",
            "2026-09-15",
        ]
    )
    assert code == 0
    out = capsys.readouterr()
    assert "ok\t" in out.out
    assert "skipped_overlap=" in out.out
    assert "skipped_parent=" in out.out
    assert "bytes_places=" in out.out
    assert "bytes_decl=" in out.out
    assert "skip overlap wd:Q90005004 table=hodonyms" in out.err
    _header, rows = read_csv(curated / "dromonyms.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["wd:Q90005001"]["parent_id"] == "iso:RU-TA"
    assert "wd:Q90005002" not in by_id
    assert "wd:Q90005004" not in by_id
    assert by_id["wd:Q58767"]["notes"].startswith("пример types.csv")
    assert by_id["wd:Q90005003"]["type_id"] == "dromonym"
    assert len(read_csv(ROOT / "data/curated/dromonyms.csv")[1]) >= 50


def test_harvest_from_json_no_network() -> None:
    places, _decls, counts, _ph, _dh = harvest(
        root=ROOT,
        today="2026-09-15",
        from_json=FIXTURE,
        from_csv=None,
        hop=False,
        hop_batch=80,
        session=None,
    )
    assert counts.incoming >= 5
    assert counts.bytes_places > 0
    assert any(row["id"] == "wd:Q58767" for row in places)
    assert any(row["id"] == "wd:Q90005001" for row in places)
    assert not any(row["id"] == "wd:Q90005002" for row in places)
    assert len(read_csv(ROOT / "data/curated/dromonyms.csv")[1]) >= 50


def test_canon_dromonyms_harvested() -> None:
    _header, rows = read_csv(ROOT / "data/curated/dromonyms.csv")
    assert len(rows) >= 50
    assert any(row["id"] == "wd:Q58767" for row in rows)
    assert any(row["abbr"] == "Транссиб" for row in rows)
    assert any(row["abbr"] == "БАМ" for row in rows)
    assert all(row["type_id"] == "dromonym" for row in rows)
    transsib = next(row for row in rows if row["id"] == "wd:Q58767")
    assert transsib["abbr"] == "Транссиб"
    assert transsib["notes"].startswith("пример types.csv")
    assert transsib["parent_id"] != "iso:RU-AD"
    assert transsib["admin1"] != "RU-AD"
    bam = next(row for row in rows if row["abbr"] == "БАМ")
    assert bam["id"] == "wd:Q377967"


def test_apply_harvest_clears_bogus_adygea_keeps_real() -> None:
    records = {
        "Q9100501": {
            "qid": "Q9100501",
            "ru": "Дорога без родителя",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "located": set(),
            "iso": set(),
        },
        "Q9100502": {
            "qid": "Q9100502",
            "ru": "Дорога в Татарстане",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "located": set(),
            "iso": {"RU-TA"},
        },
        "Q9100503": {
            "qid": "Q9100503",
            "ru": "Дорога в Адыгее",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "located": set(),
            "iso": {"RU-AD"},
        },
        "Q9100504": {
            "qid": "Q9100504",
            "ru": "Дорога нескольких субъектов",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "located": set(),
            "iso": {"RU-AD", "RU-TA"},
        },
        "Q9100505": {
            "qid": "Q9100505",
            "ru": "Новая без родителя",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "located": set(),
            "iso": set(),
        },
        "Q9100506": {
            "qid": "Q9100506",
            "ru": "Дорога в Подмосковье",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "located": set(),
            "iso": {"RU-AD", "RU-MOS"},
        },
    }
    index = load_parent_index(ROOT)
    existing = [
        _place(
            id="wd:Q9100501",
            id_scheme="wikidata",
            type_id="dromonym",
            name_ru="Дорога без родителя",
            wd="Q9100501",
            parent_id="iso:RU-AD",
            admin1="RU-AD",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-17",
            notes="keep notes",
            abbr="Транссиб",
        ),
        _place(
            id="wd:Q9100502",
            id_scheme="wikidata",
            type_id="dromonym",
            name_ru="Дорога в Татарстане",
            wd="Q9100502",
            parent_id="iso:RU-AD",
            admin1="RU-AD",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-17",
        ),
        _place(
            id="wd:Q9100503",
            id_scheme="wikidata",
            type_id="dromonym",
            name_ru="Дорога в Адыгее",
            wd="Q9100503",
            parent_id="iso:RU-AD",
            admin1="RU-AD",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-17",
        ),
        _place(
            id="wd:Q9100504",
            id_scheme="wikidata",
            type_id="dromonym",
            name_ru="Дорога нескольких субъектов",
            wd="Q9100504",
            parent_id="iso:RU-AD",
            admin1="RU-AD",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-17",
        ),
        _place(
            id="wd:Q9100506",
            id_scheme="wikidata",
            type_id="dromonym",
            name_ru="Дорога в Подмосковье",
            wd="Q9100506",
            parent_id="iso:RU-MOS",
            admin1="RU-MOS",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-17",
        ),
    ]
    places, _decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=[],
        today="2026-09-24",
        skip_map={},
    )
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q9100501"]["parent_id"] == ""
    assert by_id["wd:Q9100501"]["admin1"] == ""
    assert by_id["wd:Q9100501"]["notes"] == "keep notes"
    assert by_id["wd:Q9100501"]["abbr"] == "Транссиб"
    assert by_id["wd:Q9100502"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q9100502"]["admin1"] == "RU-TA"
    assert by_id["wd:Q9100503"]["parent_id"] == "iso:RU-AD"
    assert by_id["wd:Q9100503"]["admin1"] == "RU-AD"
    assert by_id["wd:Q9100504"]["parent_id"] == ""
    assert by_id["wd:Q9100504"]["admin1"] == ""
    assert by_id["wd:Q9100506"]["parent_id"] == "iso:RU-MOS"
    assert by_id["wd:Q9100506"]["admin1"] == "RU-MOS"
    assert "wd:Q9100505" not in by_id
    assert counts.skipped_parent >= 1
    assert counts.inserted == 0
    assert len(places) == 5
