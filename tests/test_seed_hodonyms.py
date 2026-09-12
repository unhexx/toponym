from __future__ import annotations

from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.seed_hodonyms import (
    apply_harvest,
    format_coord,
    harvest,
    is_square_name,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_hodonym,
    merge_bindings,
    qid_from_uri,
    resolve_parent,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "hodonyms_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "hodonyms-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _decl(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in DECLENSIONS_HEADER}
    row.update(kwargs)
    return row


def test_sparql_hodonyms_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    assert "Q79007" in text
    assert "Q159" in text
    assert "Q174782" in text
    assert "SELECT" in text
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_qid_and_coord_helpers() -> None:
    assert qid_from_uri("http://www.wikidata.org/entity/Q1644209") == "Q1644209"
    assert qid_from_uri("wd:Q649") == "Q649"
    assert qid_from_uri("Q656") == "Q656"
    assert qid_from_uri("") == ""
    assert format_coord("5.575E1") == "55.75"
    assert format_coord("55.749167") == "55.749167"
    assert format_coord("") == ""
    assert is_square_name("Новая площадь")
    assert not is_square_name("Тверская улица")


def test_merge_and_parent_city_beats_region() -> None:
    rows = load_rows_from_json(FIXTURE)
    merged = merge_bindings(rows)
    assert merged["Q90000001"]["ru"] == "Тестовая улица"
    assert merged["Q90000001"]["lat"] == "55.75"
    assert "Q649" in merged["Q90000001"]["located"]
    index = load_parent_index(ROOT)
    city = resolve_parent(index, {"Q649"}, {"RU-MOW"})
    assert city is not None
    assert city[0] == "wd:Q649"
    region = resolve_parent(index, {"Q1697"}, {"RU-MOS"})
    assert region is not None
    assert region[0] == "iso:RU-MOS"
    none = resolve_parent(index, {"Q1"}, set())
    assert none is None
    both = resolve_parent(index, {"Q649", "Q1697"}, {"RU-MOS"})
    assert both is not None
    assert both[0] == "wd:Q649"


def test_map_hodonym_yo_and_stable_id() -> None:
    rec = {
        "qid": "Q90000002",
        "ru": "Зелёная улица",
        "en": "Zelyonaya Street",
        "lat": "",
        "lon": "",
        "gn": "",
    }
    row = map_hodonym(rec, ("iso:RU-MOS", "RU-MOS"), "2026-09-12")
    assert row["id"] == "wd:Q90000002"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "hodonym"
    assert row["name_ru"] == "Зеленая улица"
    assert row["name_yo"] == "Зелёная улица"
    assert row["source_id"] == "wikidata"
    assert row["parent_id"] == "iso:RU-MOS"


def test_apply_harvest_upserts_skips_square_and_keeps_notes() -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(rows)
    index = load_parent_index(ROOT)
    existing = [
        _place(
            id="wd:Q1644209",
            id_scheme="wikidata",
            type_id="hodonym",
            name_ru="Тверская улица",
            parent_id="wd:Q649",
            admin1="RU-MOW",
            wd="Q1644209",
            geonames="6956712",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-11",
            notes="пример types.csv",
        )
    ]
    decls = [
        _decl(
            id="wd:Q1644209",
            type_code="hodonym",
            lemma="Тверская улица",
            paradigm="mixed_phrase",
            declinable="always",
            nom="Тверская улица",
            gen="Тверской улицы",
            review="needs_review",
            source="manual",
        )
    ]
    places, out_decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=decls,
        today="2026-09-12",
        other_ids={"Q41116"},
    )
    by_id = {row["id"]: row for row in places}
    assert counts.inserted == 2
    assert counts.skipped_square >= 2
    assert counts.skipped_parent >= 1
    assert "wd:Q90000001" in by_id
    assert by_id["wd:Q90000001"]["parent_id"] == "wd:Q649"
    assert by_id["wd:Q90000002"]["name_ru"] == "Зеленая улица"
    assert by_id["wd:Q1644209"]["notes"] == "пример types.csv"
    assert by_id["wd:Q1644209"]["geonames"] == "6956712"
    assert "wd:Q90000003" not in by_id
    assert "wd:Q41116" not in by_id
    assert "wd:Q90000004" not in by_id
    tver = next(row for row in out_decls if row["id"] == "wd:Q1644209")
    assert tver["gen"] == "Тверской улицы"
    assert tver["source"] == "manual"
    stubs = [row for row in out_decls if row["id"] == "wd:Q90000001"]
    assert len(stubs) == 1
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["source"] == "wikidata"
    assert stubs[0]["nom"] == "Тестовая улица"
    assert all(not row["id"].startswith("gn:") for row in places)


def test_cli_from_json_writes_tmp(tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    write_csv(
        curated / "hodonyms.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q1644209",
                id_scheme="wikidata",
                type_id="hodonym",
                name_ru="Тверская улица",
                parent_id="wd:Q649",
                admin1="RU-MOW",
                wd="Q1644209",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-11",
                notes="keep",
            )
        ],
    )
    write_csv(decl / "hodonyms.csv", DECLENSIONS_HEADER, [])
    for name in (
        "cities-major.csv",
        "regions.csv",
        "municipalities.csv",
        "agoronyms.csv",
        "dromonyms.csv",
    ):
        _header, rows = read_csv(ROOT / "data" / "curated" / name)
        write_csv(curated / name, _header, rows)
    (raw / "hodonyms-ru.sparql").write_text(SPARQL.read_text(encoding="utf-8"), encoding="utf-8")
    code = main(
        [
            "--root",
            str(tmp_path),
            "--from-json",
            str(FIXTURE),
            "--no-hop",
            "--today",
            "2026-09-12",
        ]
    )
    assert code == 0
    _header, rows = read_csv(curated / "hodonyms.csv")
    ids = {row["id"] for row in rows}
    assert "wd:Q90000001" in ids
    assert "wd:Q90000002" in ids
    tver = next(row for row in rows if row["id"] == "wd:Q1644209")
    assert tver["notes"] == "keep"


def test_harvest_from_json_no_network() -> None:
    places, decls, counts, _ph, _dh = harvest(
        root=ROOT,
        today="2026-09-12",
        from_json=FIXTURE,
        from_csv=None,
        hop=False,
        hop_batch=80,
        session=None,
    )
    assert counts.incoming >= 5
    assert any(row["id"] == "wd:Q1644209" for row in places)
    assert any(row["id"] == "wd:Q1644209" for row in decls)


def test_load_main_query_has_street_filter() -> None:
    query = load_main_query(SPARQL)
    assert "wdt:P31 wd:Q79007" in query
    assert "wdt:P17 wd:Q159" in query
    assert "Q174782" in query
