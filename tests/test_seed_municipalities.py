from __future__ import annotations

import json
from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.harvest import merge_bindings, resolve_parent
from scripts.seed_municipalities import (
    MUN_SKIP_RELS,
    apply_harvest,
    harvest,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_municipality,
    oktmo_digits,
    oktmo_lookup_keys,
    p31_from_query,
    queries_for_p31,
    shard_query,
    skip_ids,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "municipalities_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "municipalities-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _decl(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in DECLENSIONS_HEADER}
    row.update(kwargs)
    return row


def _copy_csv(src: Path, dest: Path) -> None:
    header, rows = read_csv(src)
    write_csv(dest, header, rows)


def _kazan_row(**kwargs: str) -> dict[str, str]:
    row = _place(
        id="local:mun:kazan-go",
        id_scheme="local",
        type_id="municipality",
        name_ru="городской округ Казань",
        name_en="Kazan Urban Okrug",
        parent_id="iso:RU-TA",
        admin1="RU-TA",
        oktmo="92701000",
        status="active",
        source_id="wikidata",
        updated_at="2026-09-11",
        notes="муниципальное образование города Казань; ойконим wd:Q900",
    )
    row.update(kwargs)
    return row


def test_sparql_municipalities_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    for qid in (
        "Q13626398",
        "Q3350075",
        "Q2198484",
        "Q60849925",
        "Q27587207",
        "Q2661988",
        "Q634099",
        "Q159",
    ):
        assert qid in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    assert "?type" in text.split("SELECT", 1)[1].split("WHERE", 1)[0]
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_load_main_query_p31_order() -> None:
    query = load_main_query(SPARQL)
    types = p31_from_query(query)
    assert types == [
        "Q13626398",
        "Q3350075",
        "Q2198484",
        "Q60849925",
        "Q27587207",
        "Q2661988",
        "Q634099",
    ]
    split = queries_for_p31(query)
    assert [qid for qid, _typed in split] == types
    assert types[-1] == "Q634099"
    for qid, typed in split:
        assert f"VALUES ?type {{ wd:{qid} }}" in typed
        assert "wd:Q13626398 wd:Q3350075" not in typed


def test_shard_query_keeps_single_type() -> None:
    query = load_main_query(SPARQL)
    typed = queries_for_p31(query)[-1][1]
    sharded = shard_query(typed, "Q5481")
    assert "VALUES ?type { wd:Q634099 }" in sharded
    assert "VALUES ?subj { wd:Q5481 }" in sharded
    assert "?item wdt:P131* ?subj" in sharded
    assert "wd:Q13626398 wd:Q3350075" not in sharded


def test_oktmo_keys_8_and_11() -> None:
    assert oktmo_digits("RU92701000") == "92701000"
    assert oktmo_lookup_keys("92701000") == ["92701000"]
    assert oktmo_lookup_keys("92701000000") == ["92701000000", "92701000"]


def test_mun_skip_rels_frozen_without_self() -> None:
    rels = {str(path).replace("\\", "/") for path in MUN_SKIP_RELS}
    assert "data/curated/municipalities.csv" not in rels
    assert "data/curated/cities-major.csv" in rels
    assert "data/curated/regions.csv" in rels
    assert "data/curated/agencies-foiv.csv" in rels


def test_map_municipality_yo_oktmo_and_stable_id() -> None:
    rec = {
        "qid": "Q90001012",
        "ru": "Городской округ Зелёный",
        "en": "Zelyony Urban Okrug",
        "lat": "",
        "lon": "",
        "gn": "",
        "oktmo": "92701000",
    }
    row = map_municipality(rec, ("iso:RU-TA", "RU-TA"), "2026-09-14")
    assert row["id"] == "wd:Q90001012"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "municipality"
    assert row["name_ru"] == "Городской округ Зеленый"
    assert row["name_yo"] == "Городской округ Зелёный"
    assert row["oktmo"] == "92701000"
    assert row["parent_id"] == "iso:RU-TA"
    assert row["source_id"] == "wikidata"


def test_parent_index_mun_before_region_no_cities() -> None:
    index = load_parent_index(ROOT)
    region = resolve_parent(index, {"Q5481"}, {"RU-TA"})
    assert region is not None
    assert region[0] == "iso:RU-TA"
    moscow = resolve_parent(index, {"Q649"}, {"RU-MOW"})
    assert moscow is not None
    assert moscow[0] == "iso:RU-MOW"
    assert moscow[0] != "wd:Q649"


def test_apply_harvest_two_pass_alias_skip_new_p576(tmp_path: Path) -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(
        rows,
        extra_scalars=("oktmo", "dissolved"),
        extra_qid_sets=("replaced", "p31"),
    )
    curated = tmp_path / "data" / "curated"
    curated.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(curated / "municipalities.csv", PLACES_HEADER, [_kazan_row()])
    write_csv(
        curated / "cities-major.csv",
        PLACES_HEADER,
        [_place(id="wd:Q900", wd="Q900", name_ru="Казань", type_id="city")],
    )
    index = load_parent_index(tmp_path)
    _header, existing = read_csv(curated / "municipalities.csv")
    skip_map = skip_ids(tmp_path)
    known = {f"wd:{qid}" for qid in records}
    known.update(row["id"] for row in existing if row.get("id"))
    known.update(f"wd:{qid}" for qid in skip_map)
    places, decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=[],
        today="2026-09-14",
        skip_map=skip_map,
        known_ids=known,
    )
    by_id = {row["id"]: row for row in places}
    assert "wd:Q90001001" in by_id
    assert by_id["wd:Q90001001"]["parent_id"] == "iso:RU-TA"
    assert "wd:Q90001002" in by_id
    assert by_id["wd:Q90001003"]["parent_id"] == "wd:Q90001002"
    assert "wd:Q90001004" not in by_id
    assert counts.skipped_other >= 1
    assert "wd:Q90001005" in by_id
    kazan = by_id["local:mun:kazan-go"]
    assert kazan["wd"] == "Q12167762"
    assert "wd:Q12167762" not in by_id
    assert kazan["notes"].startswith("муниципальное")
    assert "wd:Q90001010" not in by_id
    assert counts.skipped_parent >= 1
    assert by_id["wd:Q90001011"]["parent_id"] == "iso:RU-MOW"
    assert "wd:Q900" not in by_id
    assert counts.skipped_overlap >= 1
    stubs = [row for row in decls if row["id"] == "wd:Q90001003"]
    assert len(stubs) == 1
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["type_code"] == "municipality"
    assert stubs[0]["source"] == "wikidata"


def test_cli_from_json_writes_tmp(tmp_path: Path, capsys) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(curated / "municipalities.csv", PLACES_HEADER, [_kazan_row()])
    write_csv(decl / "municipalities.csv", DECLENSIONS_HEADER, [])
    write_csv(
        curated / "cities-major.csv",
        PLACES_HEADER,
        [_place(id="wd:Q900", wd="Q900", name_ru="Казань", type_id="city")],
    )
    sparql_text = SPARQL.read_text(encoding="utf-8")
    (raw / "municipalities-ru.sparql").write_text(sparql_text, encoding="utf-8")
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
    assert "bytes_decl=" in out.out
    assert "skip overlap wd:Q900 table=cities-major" in out.err
    _header, rows = read_csv(curated / "municipalities.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["wd:Q90001003"]["parent_id"] == "wd:Q90001002"
    assert by_id["local:mun:kazan-go"]["wd"] == "Q12167762"
    assert "wd:Q12167762" not in by_id
    assert "wd:Q900" not in by_id
    assert "wd:Q90001004" not in by_id
    assert len(read_csv(ROOT / "data/curated/municipalities.csv")[1]) >= 500


def test_cli_oktmo_11digit_alias(tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(curated / "municipalities.csv", PLACES_HEADER, [_kazan_row()])
    write_csv(decl / "municipalities.csv", DECLENSIONS_HEADER, [])
    payload = [
        {
            "item": "http://www.wikidata.org/entity/Q12167762",
            "type": "http://www.wikidata.org/entity/Q13626398",
            "ru": "городской округ Казань",
            "oktmo": "92701000000",
            "located": "http://www.wikidata.org/entity/Q5481",
            "iso": "RU-TA",
        }
    ]
    src = tmp_path / "eleven.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    code = main(
        [
            "--root",
            str(tmp_path),
            "--from-json",
            str(src),
            "--no-hop",
            "--today",
            "2026-09-14",
        ]
    )
    assert code == 0
    _header, rows = read_csv(curated / "municipalities.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["local:mun:kazan-go"]["wd"] == "Q12167762"
    assert "wd:Q12167762" not in by_id


def test_cli_deprecate_replaced_by(tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(
        curated / "municipalities.csv",
        PLACES_HEADER,
        [
            _kazan_row(),
            _place(
                id="wd:Q90001004",
                id_scheme="wikidata",
                type_id="municipality",
                name_ru="Упраздненный район",
                parent_id="iso:RU-TA",
                admin1="RU-TA",
                wd="Q90001004",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-11",
                notes="keep notes",
            ),
        ],
    )
    write_csv(decl / "municipalities.csv", DECLENSIONS_HEADER, [])
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
    _header, rows = read_csv(curated / "municipalities.csv")
    by_id = {row["id"]: row for row in rows}
    abolished = by_id["wd:Q90001004"]
    assert abolished["status"] == "deprecated"
    assert abolished["replaced_by"] == "wd:Q90001005"
    assert abolished["notes"] == "keep notes"
    assert abolished["name_ru"] == "Упраздненный район"
    assert "wd:Q12167762" not in by_id


def test_cli_deprecate_local_wd(tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(
        curated / "municipalities.csv",
        PLACES_HEADER,
        [_kazan_row(wd="Q12167762")],
    )
    write_csv(decl / "municipalities.csv", DECLENSIONS_HEADER, [])
    payload = [
        {
            "item": "http://www.wikidata.org/entity/Q12167762",
            "type": "http://www.wikidata.org/entity/Q13626398",
            "ru": "городской округ Казань",
            "dissolved": "2024-01-01T00:00:00Z",
            "located": "http://www.wikidata.org/entity/Q5481",
            "iso": "RU-TA",
        }
    ]
    src = tmp_path / "local-p576.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    code = main(
        [
            "--root",
            str(tmp_path),
            "--from-json",
            str(src),
            "--no-hop",
            "--today",
            "2026-09-14",
        ]
    )
    assert code == 0
    _header, rows = read_csv(curated / "municipalities.csv")
    by_id = {row["id"]: row for row in rows}
    local = by_id["local:mun:kazan-go"]
    assert local["status"] == "deprecated"
    assert local["notes"] == "муниципальное образование города Казань; ойконим wd:Q900"
    assert "wd:Q12167762" not in by_id


def test_harvest_from_json_no_network() -> None:
    places, decls, counts, _ph, _dh = harvest(
        root=ROOT,
        today="2026-09-14",
        from_json=FIXTURE,
        from_csv=None,
        hop=False,
        hop_batch=80,
        session=None,
    )
    assert counts.incoming >= 8
    assert any(row["id"] == "local:mun:kazan-go" for row in places)
    assert any(row["id"] == "wd:Q90001002" for row in places)
    assert len(read_csv(ROOT / "data/curated/municipalities.csv")[1]) >= 500


def test_canon_municipalities_harvested() -> None:
    _header, rows = read_csv(ROOT / "data/curated/municipalities.csv")
    assert len(rows) >= 500
    kazan = next(row for row in rows if row["id"] == "local:mun:kazan-go")
    assert kazan["wd"].startswith("Q")
    assert "wd:" + kazan["wd"] not in {row["id"] for row in rows}
    assert all(row["type_id"] == "municipality" for row in rows)
