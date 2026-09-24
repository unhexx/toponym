from __future__ import annotations

from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.harvest import HarvestCounts, merge_bindings
from scripts.seed_cities import (
    CITY_SKIP_RELS,
    LOCAL_SUBJECT_IDS,
    apply_harvest,
    harvest,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_city,
    p31_from_query,
    queries_for_p31,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "cities_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "cities-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _copy_csv(src: Path, dest: Path) -> None:
    header, rows = read_csv(src)
    write_csv(dest, header, rows)


def _noted_city(**kwargs: str) -> dict[str, str]:
    row = _place(
        id="wd:Q90003010",
        id_scheme="wikidata",
        type_id="city",
        name_ru="Город с заметкой",
        name_en="Noted City",
        parent_id="iso:RU-TA",
        admin1="RU-TA",
        wd="Q90003010",
        status="active",
        source_id="wikidata",
        updated_at="2026-09-11",
        notes="не затирать",
    )
    row.update(kwargs)
    return row


def test_sparql_cities_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    assert "Q7930989" in text
    assert "Q159" in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    assert "?type" in text.split("SELECT", 1)[1].split("WHERE", 1)[0]
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_load_main_query_city_p31() -> None:
    query = load_main_query(SPARQL)
    types = p31_from_query(query)
    assert types == ["Q7930989"]
    split = queries_for_p31(query)
    assert [qid for qid, _typed in split] == types
    typed = split[0][1]
    assert "VALUES ?type { wd:Q7930989 }" in typed


def test_city_skip_rels_frozen_without_self() -> None:
    rels = {str(path).replace("\\", "/") for path in CITY_SKIP_RELS}
    assert "data/curated/cities-major.csv" not in rels
    assert "data/curated/regions.csv" in rels
    assert "data/curated/municipalities.csv" in rels
    assert "data/curated/hodonyms.csv" in rels
    assert "data/curated/villages.csv" in rels


def test_local_subject_ids_frozen() -> None:
    assert LOCAL_SUBJECT_IDS == (
        "local:ru-crimea",
        "local:ru-sevastopol",
        "local:ru-dnr",
        "local:ru-lnr",
        "local:ru-zaporozhye",
        "local:ru-kherson",
    )


def test_harvest_counts_bytes_default_zero() -> None:
    counts = HarvestCounts()
    assert counts.bytes_places == 0
    assert counts.bytes_decl == 0


def test_map_city_yo_oktmo_and_stable_id() -> None:
    rec = {
        "qid": "Q90003005",
        "ru": "Зелёный Город",
        "en": "Zelyony Gorod",
        "lat": "55.1",
        "lon": "37.2",
        "gn": "1",
        "oktmo": "46 000 000",
    }
    row = map_city(rec, ("iso:RU-MOS", "RU-MOS"), "2026-09-15")
    assert row["id"] == "wd:Q90003005"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "city"
    assert row["name_ru"] == "Зеленый Город"
    assert row["name_yo"] == "Зелёный Город"
    assert row["parent_id"] == "iso:RU-MOS"
    assert row["oktmo"] == "46000000"
    assert row["source_id"] == "wikidata"


def test_apply_harvest_parent_overlap_crimea_and_notes() -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(
        rows, extra_scalars=("oktmo", "dissolved"), extra_qid_sets=("replaced", "p31")
    )
    index = load_parent_index(ROOT)
    existing = [
        _noted_city(),
        _place(
            id="wd:Q90003007",
            id_scheme="wikidata",
            type_id="city",
            name_ru="Старый город",
            parent_id="iso:RU-TA",
            admin1="RU-TA",
            wd="Q90003007",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-11",
            notes="keep notes",
        ),
    ]
    skip_map = {"Q90003006": "municipalities"}
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
    assert by_id["wd:Q90003001"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q90003001"]["type_id"] == "city"
    assert by_id["wd:Q90003001"]["oktmo"] == "92701000"
    assert "wd:Q90003002" not in by_id
    assert counts.skipped_parent >= 1
    assert "wd:Q90003003" not in by_id
    assert counts.skipped_other >= 1
    assert "wd:Q90003004" not in by_id
    assert "wd:Q90003006" not in by_id
    assert counts.skipped_overlap >= 1
    noted = by_id["wd:Q90003010"]
    assert noted["notes"] == "не затирать"
    assert noted["geonames"] == "123456"
    abolished = by_id["wd:Q90003007"]
    assert abolished["status"] == "deprecated"
    assert abolished["replaced_by"] == "wd:Q90003001"
    assert abolished["notes"] == "keep notes"
    assert by_id["wd:Q90003005"]["name_ru"] == "Зеленый Город"
    stubs = [row for row in decls if row["id"] == "wd:Q90003001"]
    assert len(stubs) == 1
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["type_code"] == "city"
    assert stubs[0]["source"] == "wikidata"
    assert all(row["review"] != "gold" for row in decls)


def test_apply_harvest_clears_bogus_adygea_keeps_real_parent() -> None:
    records = {
        "Q9100201": {
            "qid": "Q9100201",
            "ru": "Город без родителя",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": set(),
            "iso": set(),
            "p31": {"Q7930989"},
            "replaced": set(),
            "dissolved": "",
        },
        "Q9100202": {
            "qid": "Q9100202",
            "ru": "Город в Татарстане",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": set(),
            "iso": {"RU-TA"},
            "p31": {"Q7930989"},
            "replaced": set(),
            "dissolved": "",
        },
        "Q9100203": {
            "qid": "Q9100203",
            "ru": "Новый без родителя",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": set(),
            "iso": set(),
            "p31": {"Q7930989"},
            "replaced": set(),
            "dissolved": "",
        },
    }
    index = load_parent_index(ROOT)
    existing = [
        _place(
            id="wd:Q9100201",
            id_scheme="wikidata",
            type_id="city",
            name_ru="Город без родителя",
            wd="Q9100201",
            parent_id="iso:RU-AD",
            admin1="RU-AD",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-17",
            notes="keep notes",
        ),
        _place(
            id="wd:Q9100202",
            id_scheme="wikidata",
            type_id="city",
            name_ru="Город в Татарстане",
            wd="Q9100202",
            parent_id="iso:RU-AD",
            admin1="RU-AD",
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
        known_ids={row["id"] for row in existing},
    )
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q9100201"]["parent_id"] == ""
    assert by_id["wd:Q9100201"]["admin1"] == ""
    assert by_id["wd:Q9100201"]["notes"] == "keep notes"
    assert by_id["wd:Q9100202"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q9100202"]["admin1"] == "RU-TA"
    assert "wd:Q9100203" not in by_id
    assert counts.skipped_parent >= 1
    assert counts.inserted == 0
    assert len(places) == 2


def test_apply_harvest_keeps_specific_subject_over_lexicographic_iso() -> None:
    records = {
        "Q9100204": {
            "qid": "Q9100204",
            "ru": "Город двух субъектов",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": set(),
            "iso": {"RU-CHE", "RU-SVE"},
            "p31": {"Q7930989"},
            "replaced": set(),
            "dissolved": "",
        },
        "Q9100205": {
            "qid": "Q9100205",
            "ru": "Город с районом",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": {"Q109985990"},
            "iso": set(),
            "p31": {"Q7930989"},
            "replaced": set(),
            "dissolved": "",
        },
    }
    index = load_parent_index(ROOT)
    existing = [
        _place(
            id="wd:Q9100204",
            id_scheme="wikidata",
            type_id="city",
            name_ru="Город двух субъектов",
            wd="Q9100204",
            parent_id="iso:RU-SVE",
            admin1="RU-SVE",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-11",
        ),
        _place(
            id="wd:Q9100205",
            id_scheme="wikidata",
            type_id="city",
            name_ru="Город с районом",
            wd="Q9100205",
            parent_id="iso:RU-MOS",
            admin1="RU-MOS",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-11",
        ),
    ]
    places, _decls, counts = apply_harvest(
        records,
        index=index,
        existing_places=existing,
        existing_decls=[],
        today="2026-09-24",
        skip_map={},
        known_ids={row["id"] for row in existing},
    )
    by_id = {row["id"]: row for row in places}
    assert by_id["wd:Q9100204"]["parent_id"] == "iso:RU-SVE"
    assert by_id["wd:Q9100204"]["admin1"] == "RU-SVE"
    assert by_id["wd:Q9100204"]["updated_at"] == "2026-09-11"
    assert by_id["wd:Q9100205"]["parent_id"] == "iso:RU-MOS"
    assert by_id["wd:Q9100205"]["admin1"] == "RU-MOS"
    assert counts.inserted == 0


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
            _noted_city(),
            _place(
                id="wd:Q90003007",
                id_scheme="wikidata",
                type_id="city",
                name_ru="Старый город",
                parent_id="iso:RU-TA",
                admin1="RU-TA",
                wd="Q90003007",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-11",
                notes="keep notes",
            ),
        ],
    )
    write_csv(decl / "cities-major.csv", DECLENSIONS_HEADER, [])
    write_csv(
        curated / "municipalities.csv",
        PLACES_HEADER,
        [_place(id="wd:Q90003006", wd="Q90003006", name_ru="Перекрытие")],
    )
    (raw / "cities-ru.sparql").write_text(SPARQL.read_text(encoding="utf-8"), encoding="utf-8")
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
    assert "skip overlap wd:Q90003006 table=municipalities" in out.err
    _header, rows = read_csv(curated / "cities-major.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["wd:Q90003001"]["parent_id"] == "iso:RU-TA"
    assert "wd:Q90003002" not in by_id
    assert "wd:Q90003003" not in by_id
    assert "wd:Q90003004" not in by_id
    assert "wd:Q90003006" not in by_id
    assert by_id["wd:Q90003010"]["notes"] == "не затирать"
    assert by_id["wd:Q90003007"]["status"] == "deprecated"
    assert by_id["wd:Q90003005"]["type_id"] == "city"
    _dh, decls = read_csv(decl / "cities-major.csv")
    assert any(row["id"] == "wd:Q90003001" and row["review"] == "needs_review" for row in decls)
    assert len(read_csv(ROOT / "data/curated/cities-major.csv")[1]) >= 800


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
    assert counts.incoming >= 7
    assert counts.bytes_places > 0
    assert counts.bytes_decl > 0
    assert any(row["id"] == "wd:Q649" for row in places)
    assert any(row["id"] == "wd:Q90003001" for row in places)
    assert not any(row["id"] == "wd:Q90003003" for row in places)
    assert len(read_csv(ROOT / "data/curated/cities-major.csv")[1]) >= 800


def test_canon_cities_major_harvested() -> None:
    _header, rows = read_csv(ROOT / "data/curated/cities-major.csv")
    assert len(rows) >= 800
    assert any(row["id"] == "wd:Q649" for row in rows)
    assert any(row["name_ru"] == "Самара" for row in rows)
    assert all(row["type_id"] == "city" for row in rows)
