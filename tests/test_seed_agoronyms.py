from __future__ import annotations

from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.harvest import merge_bindings
from scripts.seed_agoronyms import (
    AGO_SKIP_RELS,
    apply_harvest,
    harvest,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_agoronym,
    p31_from_query,
    queries_for_p31,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "agoronyms_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "agoronyms-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _copy_csv(src: Path, dest: Path) -> None:
    header, rows = read_csv(src)
    write_csv(dest, header, rows)


def _krasnaya(**kwargs: str) -> dict[str, str]:
    row = _place(
        id="wd:Q41116",
        id_scheme="wikidata",
        type_id="agoronym",
        name_ru="Красная площадь",
        name_en="Red Square",
        parent_id="wd:Q649",
        admin1="RU-MOW",
        lat="55.754167",
        lon="37.620000",
        wd="Q41116",
        geonames="6295575",
        status="active",
        source_id="wikidata",
        updated_at="2026-09-12",
        notes="пример types.csv; площадь, не улица",
    )
    row.update(kwargs)
    return row


def test_sparql_agoronyms_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    assert "Q174782" in text
    assert "Q159" in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    assert "?type" in text.split("SELECT", 1)[1].split("WHERE", 1)[0]
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_load_main_query_agoronym_p31() -> None:
    query = load_main_query(SPARQL)
    types = p31_from_query(query)
    assert types == ["Q174782"]
    split = queries_for_p31(query)
    assert [qid for qid, _typed in split] == types
    assert "VALUES ?type { wd:Q174782 }" in split[0][1]


def test_ago_skip_rels_frozen_without_self() -> None:
    rels = {str(path).replace("\\", "/") for path in AGO_SKIP_RELS}
    assert "data/curated/agoronyms.csv" not in rels
    assert "data/curated/hodonyms.csv" in rels
    assert "data/curated/cities-major.csv" in rels
    assert "data/curated/municipalities.csv" in rels


def test_map_agoronym_yo_and_stable_id() -> None:
    rec = {
        "qid": "Q90004003",
        "ru": "Зелёная площадь",
        "en": "Zelyonaya Square",
        "lat": "",
        "lon": "",
        "gn": "",
    }
    row = map_agoronym(rec, ("wd:Q656", "RU-SPE"), "2026-09-15")
    assert row["id"] == "wd:Q90004003"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "agoronym"
    assert row["name_ru"] == "Зеленая площадь"
    assert row["name_yo"] == "Зелёная площадь"
    assert row["parent_id"] == "wd:Q656"
    assert row["source_id"] == "wikidata"


def test_apply_harvest_city_parent_keeps_notes_skips_overlap() -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(rows, extra_qid_sets=("p31",))
    index = load_parent_index(ROOT)
    existing = [_krasnaya()]
    skip_map = {"Q90004004": "hodonyms"}
    places, decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=[],
        today="2026-09-15",
        skip_map=skip_map,
    )
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q90004001"]["parent_id"] == "wd:Q649"
    assert by_id["wd:Q90004001"]["type_id"] == "agoronym"
    assert "wd:Q90004002" not in by_id
    assert counts.skipped_parent >= 1
    assert "wd:Q90004004" not in by_id
    assert counts.skipped_overlap >= 1
    krasnaya = by_id["wd:Q41116"]
    assert krasnaya["notes"].startswith("пример types.csv")
    assert krasnaya["geonames"] == "6295575"
    assert by_id["wd:Q90004003"]["name_ru"] == "Зеленая площадь"
    stubs = [row for row in decls if row["id"] == "wd:Q90004001"]
    assert len(stubs) == 1
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["type_code"] == "agoronym"
    assert stubs[0]["source"] == "wikidata"
    assert all(row["review"] != "gold" for row in decls)


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
        curated / "hodonyms.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q90004004",
                wd="Q90004004",
                name_ru="Перекрытие с улицей",
                type_id="hodonym",
            )
        ],
    )
    write_csv(curated / "agoronyms.csv", PLACES_HEADER, [_krasnaya()])
    write_csv(decl / "agoronyms.csv", DECLENSIONS_HEADER, [])
    (raw / "agoronyms-ru.sparql").write_text(SPARQL.read_text(encoding="utf-8"), encoding="utf-8")
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
    assert "skip overlap wd:Q90004004 table=hodonyms" in out.err
    _header, rows = read_csv(curated / "agoronyms.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["wd:Q90004001"]["parent_id"] == "wd:Q649"
    assert "wd:Q90004002" not in by_id
    assert "wd:Q90004004" not in by_id
    assert by_id["wd:Q41116"]["notes"].startswith("пример types.csv")
    assert by_id["wd:Q90004003"]["type_id"] == "agoronym"
    assert len(read_csv(ROOT / "data/curated/agoronyms.csv")[1]) == 5


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
    assert any(row["id"] == "wd:Q41116" for row in places)
    assert any(row["id"] == "wd:Q90004001" for row in places)
    assert not any(row["id"] == "wd:Q90004002" for row in places)
    assert len(read_csv(ROOT / "data/curated/agoronyms.csv")[1]) == 5


def test_canon_agoronyms_still_seed() -> None:
    _header, rows = read_csv(ROOT / "data/curated/agoronyms.csv")
    assert len(rows) == 5
    assert any(row["id"] == "wd:Q41116" for row in rows)
    assert any(row["name_ru"] == "Красная площадь" for row in rows)
    assert all(row["type_id"] == "agoronym" for row in rows)
