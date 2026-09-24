from __future__ import annotations

import time
from pathlib import Path

import pytest

from scripts.lib.csvio import PLACES_HEADER, write_csv
from scripts.lib.harvest import (
    ALIAS_FILL,
    KNOWN_FILL,
    KNOWN_IDS_QUERY,
    LOCATED_QUERY,
    SeedError,
    collect_known_qids,
    fetch_sharded,
    incoming_deprecate,
    incoming_for_upsert,
    known_ids_queries,
    load_main_query,
    mapped_known_fields,
    merge_bindings,
    qid_of_place,
    queries_for_p31,
    region_wd_qids,
    shard_query,
    skip_ids,
)
from scripts.lib.places import load_index_relpaths


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def test_load_main_query_rejects_sparql_without_values(tmp_path: Path) -> None:
    path = tmp_path / "no-values.sparql"
    path.write_text("SELECT ?item WHERE { ?item wdt:P31 wd:Q515 . }\n", encoding="utf-8")
    with pytest.raises(SeedError, match="VALUES"):
        load_main_query(path)


def test_load_main_query_accepts_values_without_hodonym_qid(tmp_path: Path) -> None:
    path = tmp_path / "mun.sparql"
    path.write_text(
        "SELECT ?item WHERE {\n  VALUES ?type { wd:Q13626398 }\n}\n",
        encoding="utf-8",
    )
    query = load_main_query(path)
    assert "Q13626398" in query
    assert "VALUES" in query


def test_queries_for_p31_moves_last() -> None:
    query = "SELECT ?item WHERE {\n  VALUES ?type { wd:Q1 wd:Q2 wd:Q3 }\n}"
    split = queries_for_p31(query, last=("Q3",))
    assert [qid for qid, _typed in split] == ["Q1", "Q2", "Q3"]
    empty_last = queries_for_p31(query, last=())
    assert [qid for qid, _typed in empty_last] == ["Q1", "Q2", "Q3"]


def test_merge_bindings_extra_scalars_and_qid_sets() -> None:
    rows = [
        {
            "item": "http://www.wikidata.org/entity/Q1",
            "ru": "Район",
            "type": "http://www.wikidata.org/entity/Q2198484",
            "oktmo": "92701000",
            "dissolved": "2020-01-01T00:00:00Z",
            "replaced": "http://www.wikidata.org/entity/Q2",
        },
        {
            "item": "Q1",
            "p31": "wd:Q60849925",
            "replaced": "wd:Q3",
            "oktmo": "999",
        },
    ]
    merged = merge_bindings(
        rows,
        extra_scalars=("oktmo", "dissolved"),
        extra_qid_sets=("replaced", "p31"),
    )
    rec = merged["Q1"]
    assert rec["oktmo"] == "92701000"
    assert rec["dissolved"].startswith("2020-01-01")
    assert rec["p31"] == {"Q2198484", "Q60849925"}
    assert rec["replaced"] == {"Q2", "Q3"}


def test_incoming_for_upsert_alias_fill_wd() -> None:
    mapped = {
        "id": "local:mun:kazan-go",
        "wd": "Q12167762",
        "lat": "55.8",
        "name_ru": "новое",
    }
    existing = {
        "id": "local:mun:kazan-go",
        "wd": "",
        "lat": "55.7",
        "name_ru": "Казань",
    }
    inc = incoming_for_upsert(mapped, existing, fill=ALIAS_FILL)
    assert inc is not None
    assert inc["id"] == "local:mun:kazan-go"
    assert inc["wd"] == "Q12167762"
    assert "lat" not in inc
    assert "name_ru" not in inc


def test_incoming_deprecate_canon_id() -> None:
    row = incoming_deprecate("local:mun:kazan-go", "wd:Q9", "2026-09-14")
    assert row == {
        "id": "local:mun:kazan-go",
        "status": "deprecated",
        "updated_at": "2026-09-14",
        "replaced_by": "wd:Q9",
    }
    empty = incoming_deprecate("wd:Q1", "", "2026-09-14")
    assert "replaced_by" not in empty


def test_skip_ids_missing_files_and_resource_name(tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    curated.mkdir(parents=True)
    write_csv(
        curated / "cities-major.csv",
        PLACES_HEADER,
        [_place(id="wd:Q649", wd="Q649", name_ru="Москва")],
    )
    rels = (
        Path("data/curated/cities-major.csv"),
        Path("data/curated/agoronyms.csv"),
    )
    out = skip_ids(tmp_path, rels)
    assert out["Q649"] == "cities-major"
    assert "agoronyms" not in out.values()


def test_collect_known_qids_unifies_tables(tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    curated.mkdir(parents=True)
    write_csv(
        curated / "cities-major.csv",
        PLACES_HEADER,
        [_place(id="wd:Q649", wd="", name_ru="Москва")],
    )
    write_csv(
        curated / "municipalities.csv",
        PLACES_HEADER,
        [_place(id="local:mun:kazan-go", wd="Q12167762", name_ru="Казань")],
    )
    write_csv(
        curated / "hodonyms.csv",
        PLACES_HEADER,
        [_place(id="wd:Q1644209", wd="Q1644209", name_ru="Тверская улица")],
    )
    write_csv(
        curated / "microtoponyms.csv",
        PLACES_HEADER,
        [_place(id="wd:Q22698", wd="Q22698", name_ru="парк")],
    )
    write_csv(
        curated / "villages.csv",
        PLACES_HEADER,
        [_place(id="wd:Q894049", wd="Q894049", name_ru="Бородино")],
    )
    write_csv(
        curated / "hydronyms-major.csv",
        PLACES_HEADER,
        [_place(id="wd:Q626", wd="Q626", name_ru="Волга")],
    )
    write_csv(
        curated / "oronyms-major.csv",
        PLACES_HEADER,
        [_place(id="wd:Q43105", wd="", name_ru="Эльбрус")],
    )
    write_csv(
        curated / "agoronyms.csv",
        PLACES_HEADER,
        [_place(id="wd:Q41116", wd="Q41116", name_ru="Красная площадь")],
    )
    write_csv(
        curated / "dromonyms.csv",
        PLACES_HEADER,
        [_place(id="wd:Q58767", wd="Q58767", name_ru="Транссиб")],
    )
    write_csv(
        curated / "agencies-foiv.csv",
        PLACES_HEADER,
        [_place(id="foiv:mvd", wd="Q1192838", name_ru="МВД")],
    )
    rels = (
        "data/curated/cities-major.csv",
        "data/curated/municipalities.csv",
        "data/curated/hodonyms.csv",
        "data/curated/microtoponyms.csv",
        "data/curated/villages.csv",
        "data/curated/hydronyms-major.csv",
        "data/curated/oronyms-major.csv",
        "data/curated/agoronyms.csv",
        "data/curated/dromonyms.csv",
        "data/curated/agencies-foiv.csv",
        "data/curated/missing.csv",
    )
    qids = collect_known_qids(tmp_path, rels)
    assert qids == [
        "Q649",
        "Q12167762",
        "Q1644209",
        "Q22698",
        "Q894049",
        "Q626",
        "Q43105",
        "Q41116",
        "Q58767",
        "Q1192838",
    ]
    assert qid_of_place({"id": "local:mun:x", "wd": "Q1"}) == "Q1"
    assert qid_of_place({"id": "foiv:mvd", "wd": "Q1192838"}) == "Q1192838"


def test_collect_known_qids_canon_includes_new_harvests() -> None:
    root = Path(__file__).resolve().parents[1]
    rels = load_index_relpaths(root)
    for rel in (
        "data/curated/villages.csv",
        "data/curated/hydronyms-major.csv",
        "data/curated/oronyms-major.csv",
        "data/curated/agoronyms.csv",
        "data/curated/dromonyms.csv",
        "data/curated/agencies-foiv.csv",
    ):
        assert rel in rels
    qids = set(collect_known_qids(root, rels))
    assert "Q894049" in qids
    assert "Q626" in qids
    assert "Q43105" in qids
    assert "Q41116" in qids
    assert "Q58767" in qids
    assert "Q1192838" in qids
    assert "Q649" in qids


def test_known_ids_queries_batches_values() -> None:
    queries = known_ids_queries(["Q1", "Q2", "Q3"], batch_size=2)
    assert len(queries) == 2
    assert "VALUES ?item { wd:Q1 wd:Q2 }" in queries[0]
    assert "VALUES ?item { wd:Q3 }" in queries[1]
    assert "P625" in queries[0]
    assert "P1566" in queries[0]
    assert "P764" in queries[0]
    assert "%s" not in queries[0]
    assert "VALUES ?item { %s }" in KNOWN_IDS_QUERY
    assert known_ids_queries([]) == []
    assert "VALUES ?item { %s }" in LOCATED_QUERY
    assert "wdt:P131*" in LOCATED_QUERY


def test_mapped_known_fields_fill_tuple() -> None:
    rec = {
        "qid": "Q649",
        "ru": "Москва",
        "en": "Moscow",
        "lat": "55.75",
        "lon": "37.61",
        "gn": "524901",
        "oktmo": "45 000 000",
    }
    mapped = mapped_known_fields(rec)
    assert mapped["id"] == "wd:Q649"
    assert mapped["wd"] == "Q649"
    assert mapped["geonames"] == "524901"
    assert mapped["oktmo"] == "45000000"
    assert "name_ru" not in mapped
    existing = {"id": "wd:Q649", "lat": "55.7", "geonames": "", "name_en": ""}
    inc = incoming_for_upsert(mapped, existing, fill=KNOWN_FILL)
    assert inc is not None
    assert "lat" not in inc
    assert inc["geonames"] == "524901"
    assert inc["name_en"] == "Moscow"


def test_shard_query_injects_region_values() -> None:
    query = "SELECT ?item WHERE {\n  VALUES ?type { wd:Q532 }\n  ?item wdt:P31 ?type .\n}"
    sharded = shard_query(query, "Q5481")
    assert "VALUES ?type { wd:Q532 }" in sharded
    assert "VALUES ?subj { wd:Q5481 }" in sharded
    assert "?item wdt:P131* ?subj" in sharded
    with pytest.raises(SeedError, match="VALUES"):
        shard_query("SELECT ?item WHERE { ?item wdt:P31 wd:Q532 . }", "Q5481")


def test_region_wd_qids_all_subjects() -> None:
    root = Path(__file__).resolve().parents[1]
    qids = region_wd_qids(root)
    assert len(qids) == 89
    assert all(qid.startswith("Q") for qid in qids)
    assert len(set(qids)) == 89


def test_fetch_sharded_wall_sec_zero_visits_all() -> None:
    seen: list[str] = []

    def fake_fetch(region_qid: str) -> list[dict[str, str]]:
        seen.append(region_qid)
        return []

    qids = [f"Q{i}" for i in range(89)]
    rows = fetch_sharded(
        None, "SELECT ?item WHERE { VALUES ?type { wd:Q532 } }", qids,
        wall_sec=0, fetch=fake_fetch,
    )
    assert rows == []
    assert seen == qids


def test_fetch_sharded_wall_sec_stops_early() -> None:
    seen: list[str] = []

    def fake_fetch(region_qid: str) -> list[dict[str, str]]:
        seen.append(region_qid)
        time.sleep(0.02)
        return []

    qids = [f"Q{i}" for i in range(89)]
    fetch_sharded(
        None, "SELECT ?item WHERE { VALUES ?type { wd:Q532 } }", qids,
        wall_sec=0.001, fetch=fake_fetch,
    )
    assert 0 < len(seen) < 89
