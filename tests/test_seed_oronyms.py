from __future__ import annotations

from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.harvest import merge_bindings
from scripts.seed_oronyms import (
    ORO_SKIP_RELS,
    apply_harvest,
    harvest,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_oronym,
    p31_from_query,
    queries_for_p31,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "oronyms_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "oronyms-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _copy_csv(src: Path, dest: Path) -> None:
    header, rows = read_csv(src)
    write_csv(dest, header, rows)


def _elbrus(**kwargs: str) -> dict[str, str]:
    row = _place(
        id="wd:Q43105",
        id_scheme="wikidata",
        type_id="oronym",
        name_ru="Эльбрус",
        name_en="Mount Elbrus",
        wd="Q43105",
        geonames="563532",
        status="active",
        source_id="wikidata",
        updated_at="2026-09-09",
        notes="keep notes",
    )
    row.update(kwargs)
    return row


def test_sparql_oronyms_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    assert "Q8502" in text
    assert "Q46831" in text
    assert "Q8072" in text
    assert "Q23442" in text
    assert "Q34763" in text
    assert "Q159" in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_load_main_query_oronym_p31_order() -> None:
    query = load_main_query(SPARQL)
    types = p31_from_query(query)
    assert types == ["Q8502", "Q46831", "Q8072", "Q23442", "Q34763"]
    split = queries_for_p31(query)
    assert [qid for qid, _typed in split] == types
    assert query.count("SELECT") == 1
    joined = " ".join(f"wd:{qid}" for qid in types)
    assert joined in query
    for qid, typed in split:
        assert f"VALUES ?type {{ wd:{qid} }}" in typed
        assert joined not in typed


def test_oro_skip_rels_frozen_without_self() -> None:
    rels = {str(path).replace("\\", "/") for path in ORO_SKIP_RELS}
    assert "data/curated/oronyms-major.csv" not in rels
    assert "data/curated/hydronyms-major.csv" in rels
    assert "data/curated/cities-major.csv" in rels
    assert "data/curated/regions.csv" in rels
    assert "data/curated/villages.csv" in rels


def test_map_oronym_yo_oktmo_and_stable_id() -> None:
    rec = {
        "qid": "Q90008007",
        "ru": "Зелёный полуостров",
        "en": "Zelyony Peninsula",
        "lat": "54.1",
        "lon": "39.2",
        "gn": "1",
        "oktmo": "46 000 000",
        "p31": {"Q34763"},
    }
    row = map_oronym(rec, ("iso:RU-MOS", "RU-MOS"), "2026-09-15")
    assert row["id"] == "wd:Q90008007"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "insulonym"
    assert row["name_ru"] == "Зеленый полуостров"
    assert row["name_yo"] == "Зелёный полуостров"
    assert row["parent_id"] == "iso:RU-MOS"
    assert row["oktmo"] == "46000000"
    assert row["source_id"] == "wikidata"


def test_apply_harvest_empty_parent_keeps_gold_skips_lake() -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(
        rows, extra_scalars=("oktmo", "dissolved"), extra_qid_sets=("replaced", "p31")
    )
    index = load_parent_index(ROOT)
    existing = [
        _elbrus(),
        _place(
            id="wd:Q35600",
            id_scheme="wikidata",
            type_id="oronym",
            name_ru="Уральские горы",
            name_en="Ural Mountains",
            wd="Q35600",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-09",
        ),
        _place(
            id="wd:Q7792",
            id_scheme="wikidata",
            type_id="insulonym",
            name_ru="Сахалин",
            name_en="Sakhalin",
            wd="Q7792",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-09",
        ),
        _place(
            id="wd:Q90008006",
            id_scheme="wikidata",
            type_id="oronym",
            name_ru="Старая гора",
            wd="Q90008006",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-11",
            notes="keep notes",
        ),
    ]
    skip_map = {"Q90008004": "cities-major"}
    known = {f"wd:{qid}" for qid in records}
    known.update(row["id"] for row in existing if row.get("id"))
    gold = {
        "id": "wd:Q43105",
        "type_code": "oronym",
        "lemma": "Эльбрус",
        "review": "gold",
        "source": "manual",
    }
    gold.update({key: "" for key in DECLENSIONS_HEADER if key not in gold})
    places, decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=[gold],
        today="2026-09-15",
        skip_map=skip_map,
        known_ids=known,
    )
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q90008001"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q90008001"]["type_id"] == "oronym"
    assert by_id["wd:Q90008002"]["type_id"] == "oronym"
    assert by_id["wd:Q90008002"]["parent_id"] == ""
    assert "wd:Q90008003" not in by_id
    assert counts.skipped_other >= 1
    assert "wd:Q90008004" not in by_id
    assert counts.skipped_overlap >= 1
    assert "wd:Q90008005" not in by_id
    assert "wd:Q90008008" not in by_id
    elbrus = by_id["wd:Q43105"]
    assert elbrus["notes"] == "keep notes"
    assert elbrus["type_id"] == "oronym"
    assert by_id["wd:Q7792"]["type_id"] == "insulonym"
    abolished = by_id["wd:Q90008006"]
    assert abolished["status"] == "deprecated"
    assert abolished["replaced_by"] == "wd:Q90008001"
    assert abolished["notes"] == "keep notes"
    assert by_id["wd:Q90008007"]["name_ru"] == "Зеленый полуостров"
    assert by_id["wd:Q90008007"]["type_id"] == "insulonym"
    assert by_id["wd:Q90008009"]["type_id"] == "oronym"
    stubs = [row for row in decls if row["id"] == "wd:Q90008001"]
    assert len(stubs) == 1
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["type_code"] == "oronym"
    assert stubs[0]["source"] == "wikidata"
    gold_rows = [row for row in decls if row["id"] == "wd:Q43105"]
    assert gold_rows == [gold]


def test_cli_from_json_writes_tmp(tmp_path: Path, capsys) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(
        curated / "cities-major.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q90008004",
                wd="Q90008004",
                name_ru="Перекрытие с городом",
                type_id="city",
            )
        ],
    )
    write_csv(
        curated / "oronyms-major.csv",
        PLACES_HEADER,
        [
            _elbrus(),
            _place(
                id="wd:Q35600",
                id_scheme="wikidata",
                type_id="oronym",
                name_ru="Уральские горы",
                wd="Q35600",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-09",
            ),
            _place(
                id="wd:Q7792",
                id_scheme="wikidata",
                type_id="insulonym",
                name_ru="Сахалин",
                wd="Q7792",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-09",
            ),
            _place(
                id="wd:Q90008006",
                id_scheme="wikidata",
                type_id="oronym",
                name_ru="Старая гора",
                wd="Q90008006",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-11",
                notes="keep notes",
            ),
        ],
    )
    write_csv(decl / "oronyms-major.csv", DECLENSIONS_HEADER, [])
    (raw / "oronyms-ru.sparql").write_text(SPARQL.read_text(encoding="utf-8"), encoding="utf-8")
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
    assert "skipped_other=" in out.out
    assert "skipped_overlap=" in out.out
    assert "bytes_places=" in out.out
    assert "bytes_decl=" in out.out
    assert "skip overlap wd:Q90008004 table=cities-major" in out.err
    _header, rows = read_csv(curated / "oronyms-major.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["wd:Q90008001"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q90008001"]["type_id"] == "oronym"
    assert by_id["wd:Q90008002"]["parent_id"] == ""
    assert "wd:Q90008003" not in by_id
    assert "wd:Q90008004" not in by_id
    assert "wd:Q90008005" not in by_id
    assert "wd:Q90008008" not in by_id
    assert by_id["wd:Q43105"]["notes"] == "keep notes"
    assert by_id["wd:Q7792"]["type_id"] == "insulonym"
    assert by_id["wd:Q90008006"]["status"] == "deprecated"
    assert by_id["wd:Q90008007"]["type_id"] == "insulonym"
    assert by_id["wd:Q90008009"]["type_id"] == "oronym"
    assert len(read_csv(ROOT / "data/curated/oronyms-major.csv")[1]) >= 5000


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
    assert counts.incoming >= 10
    assert counts.bytes_places > 0
    assert any(row["id"] == "wd:Q43105" for row in places)
    assert any(row["id"] == "wd:Q35600" for row in places)
    assert any(row["id"] == "wd:Q7792" for row in places)
    assert any(row["id"] == "wd:Q90008001" for row in places)
    assert any(row["id"] == "wd:Q90008002" for row in places)
    assert not any(row["id"] == "wd:Q90008008" for row in places)
    assert len(read_csv(ROOT / "data/curated/oronyms-major.csv")[1]) >= 5000


def test_harvest_live_per_type(monkeypatch, tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(curated / "cities-major.csv", PLACES_HEADER, [])
    write_csv(curated / "oronyms-major.csv", PLACES_HEADER, [_elbrus()])
    write_csv(decl / "oronyms-major.csv", DECLENSIONS_HEADER, [])
    (raw / "oronyms-ru.sparql").write_text(SPARQL.read_text(encoding="utf-8"), encoding="utf-8")
    calls: list[str] = []

    def fake_sparql(_session, query: str, timeout: int = 90):
        calls.append(query)
        types = p31_from_query(query)
        assert len(types) == 1
        p31 = types[0]
        if p31 == "Q8502":
            return [
                {
                    "item": "http://www.wikidata.org/entity/Q43105",
                    "type": "http://www.wikidata.org/entity/Q8502",
                    "ru": "Эльбрус",
                    "en": "Mount Elbrus",
                }
            ]
        if p31 == "Q23442":
            return [
                {
                    "item": "http://www.wikidata.org/entity/Q7792",
                    "type": "http://www.wikidata.org/entity/Q23442",
                    "ru": "Сахалин",
                    "en": "Sakhalin",
                }
            ]
        return []

    monkeypatch.setattr("scripts.seed_oronyms.sparql_csv", fake_sparql)
    monkeypatch.setattr("scripts.seed_oronyms.time.sleep", lambda _s: None)
    places, _decls, _counts, _ph, _dh = harvest(
        root=tmp_path,
        today="2026-09-15",
        from_json=None,
        from_csv=None,
        hop=False,
        hop_batch=80,
        session=object(),  # type: ignore[arg-type]
    )
    assert [p31_from_query(query)[0] for query in calls] == [
        "Q8502",
        "Q46831",
        "Q8072",
        "Q23442",
        "Q34763",
    ]
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q43105"]["type_id"] == "oronym"
    assert by_id["wd:Q7792"]["type_id"] == "insulonym"


def test_canon_oronyms_harvested() -> None:
    _header, rows = read_csv(ROOT / "data/curated/oronyms-major.csv")
    assert len(rows) >= 5000
    assert any(row["id"] == "wd:Q43105" and row["name_ru"] == "Эльбрус" for row in rows)
    assert any(row["id"] == "wd:Q35600" and row["name_ru"] == "Уральские горы" for row in rows)
    assert any(row["id"] == "wd:Q7792" and row["type_id"] == "insulonym" for row in rows)
    assert not any(row["id"] == "wd:Q5513" for row in rows)
    assert {row["type_id"] for row in rows} <= {"oronym", "insulonym"}
