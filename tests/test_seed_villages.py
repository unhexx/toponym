from __future__ import annotations

from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.harvest import merge_bindings
from scripts.seed_villages import (
    VIL_SKIP_RELS,
    apply_harvest,
    harvest,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_village,
    p31_from_query,
    queries_for_p31,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "villages_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "villages-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _copy_csv(src: Path, dest: Path) -> None:
    header, rows = read_csv(src)
    write_csv(dest, header, rows)


def _borodino(**kwargs: str) -> dict[str, str]:
    row = _place(
        id="wd:Q894049",
        id_scheme="wikidata",
        type_id="village",
        name_ru="Бородино",
        name_en="Borodino",
        parent_id="iso:RU-MOS",
        admin1="RU-MOS",
        wd="Q894049",
        geonames="572278",
        status="active",
        source_id="wikidata",
        updated_at="2026-09-12",
        notes="пример types.csv; деревня, Можайский округ; не город Бородино",
    )
    row.update(kwargs)
    return row


def test_sparql_villages_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    assert "Q15078955" in text
    assert "Q532" in text
    assert "Q159" in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    assert "Q5084" not in text.split("VALUES ?type", 1)[1].split("}", 1)[0]
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_load_main_query_village_p31_q532_last() -> None:
    query = load_main_query(SPARQL)
    types = p31_from_query(query)
    assert types == ["Q15078955", "Q532"]
    split = queries_for_p31(query)
    assert [qid for qid, _typed in split] == types
    assert types[-1] == "Q532"
    for qid, typed in split:
        assert f"VALUES ?type {{ wd:{qid} }}" in typed
        assert "wd:Q15078955 wd:Q532" not in typed


def test_vil_skip_rels_frozen_without_self() -> None:
    rels = {str(path).replace("\\", "/") for path in VIL_SKIP_RELS}
    assert "data/curated/villages.csv" not in rels
    assert "data/curated/cities-major.csv" in rels
    assert "data/curated/municipalities.csv" in rels
    assert "data/curated/regions.csv" in rels


def test_map_village_yo_oktmo_and_stable_id() -> None:
    rec = {
        "qid": "Q90006008",
        "ru": "Зелёная деревня",
        "en": "Zelyonaya Derevnya",
        "lat": "54.1",
        "lon": "39.2",
        "gn": "1",
        "oktmo": "46 000 000",
    }
    row = map_village(rec, ("iso:RU-MOS", "RU-MOS"), "2026-09-15")
    assert row["id"] == "wd:Q90006008"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "village"
    assert row["name_ru"] == "Зеленая деревня"
    assert row["name_yo"] == "Зелёная деревня"
    assert row["parent_id"] == "iso:RU-MOS"
    assert row["oktmo"] == "46000000"
    assert row["source_id"] == "wikidata"


def test_apply_harvest_p576_overlap_hamlet_and_notes() -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(
        rows, extra_scalars=("oktmo", "dissolved"), extra_qid_sets=("replaced", "p31")
    )
    index = load_parent_index(ROOT)
    existing = [
        _borodino(),
        _place(
            id="wd:Q90006006",
            id_scheme="wikidata",
            type_id="village",
            name_ru="Старое село",
            parent_id="iso:RU-TA",
            admin1="RU-TA",
            wd="Q90006006",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-11",
            notes="keep notes",
        ),
    ]
    skip_map = {"Q90006004": "cities-major"}
    known = {f"wd:{qid}" for qid in records}
    known.update(row["id"] for row in existing if row.get("id"))
    places, decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=[],
        today="2026-09-15",
        skip_map=skip_map,
        known_ids=known,
    )
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q90006001"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q90006001"]["type_id"] == "village"
    assert by_id["wd:Q90006001"]["oktmo"] == "92701000"
    assert by_id["wd:Q90006002"]["type_id"] == "village"
    assert "wd:Q90006003" not in by_id
    assert counts.skipped_parent >= 1
    assert "wd:Q90006004" not in by_id
    assert counts.skipped_overlap >= 1
    assert "wd:Q90006005" not in by_id
    assert "wd:Q90006007" not in by_id
    assert counts.skipped_other >= 1
    noted = by_id["wd:Q894049"]
    assert noted["notes"].startswith("пример types.csv")
    abolished = by_id["wd:Q90006006"]
    assert abolished["status"] == "deprecated"
    assert abolished["replaced_by"] == "wd:Q90006001"
    assert abolished["notes"] == "keep notes"
    assert by_id["wd:Q90006008"]["name_ru"] == "Зеленая деревня"
    stubs = [row for row in decls if row["id"] == "wd:Q90006001"]
    assert len(stubs) == 1
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["type_code"] == "village"
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
    write_csv(
        curated / "cities-major.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q90006004",
                wd="Q90006004",
                name_ru="Перекрытие с городом",
                type_id="city",
            )
        ],
    )
    write_csv(
        curated / "municipalities.csv",
        PLACES_HEADER,
        [_place(id="wd:Q12167762", wd="Q12167762", name_ru="ГО Казань")],
    )
    write_csv(
        curated / "villages.csv",
        PLACES_HEADER,
        [
            _borodino(),
            _place(
                id="wd:Q90006006",
                id_scheme="wikidata",
                type_id="village",
                name_ru="Старое село",
                parent_id="iso:RU-TA",
                admin1="RU-TA",
                wd="Q90006006",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-11",
                notes="keep notes",
            ),
        ],
    )
    write_csv(decl / "villages.csv", DECLENSIONS_HEADER, [])
    (raw / "villages-ru.sparql").write_text(
        SPARQL.read_text(encoding="utf-8"), encoding="utf-8"
    )
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
    assert "skipped_parent=" in out.out
    assert "bytes_places=" in out.out
    assert "bytes_decl=" in out.out
    assert "skip overlap wd:Q90006004 table=cities-major" in out.err
    _header, rows = read_csv(curated / "villages.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["wd:Q90006001"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q90006001"]["type_id"] == "village"
    assert "wd:Q90006003" not in by_id
    assert "wd:Q90006004" not in by_id
    assert "wd:Q90006005" not in by_id
    assert "wd:Q90006007" not in by_id
    assert by_id["wd:Q894049"]["notes"].startswith("пример types.csv")
    assert by_id["wd:Q90006006"]["status"] == "deprecated"
    assert by_id["wd:Q90006008"]["type_id"] == "village"
    assert len(read_csv(ROOT / "data/curated/villages.csv")[1]) >= 5000


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
    assert counts.incoming >= 8
    assert counts.bytes_places > 0
    assert counts.bytes_decl > 0
    assert any(row["id"] == "wd:Q894049" for row in places)
    assert any(row["id"] == "wd:Q90006001" for row in places)
    assert not any(row["id"] == "wd:Q90006007" for row in places)
    assert len(read_csv(ROOT / "data/curated/villages.csv")[1]) >= 5000


def test_canon_villages_harvested() -> None:
    _header, rows = read_csv(ROOT / "data/curated/villages.csv")
    assert len(rows) >= 5000
    assert any(row["id"] == "wd:Q894049" for row in rows)
    assert any(row["name_ru"] == "Бородино" for row in rows)
    assert any(row["name_ru"] == "Вешенская" for row in rows)
    assert all(row["type_id"] == "village" for row in rows)
