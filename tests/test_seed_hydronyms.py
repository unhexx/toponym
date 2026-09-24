from __future__ import annotations

from pathlib import Path

from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.declensions import DECLENSIONS_HEADER
from scripts.lib.harvest import SeedError, merge_bindings
from scripts.seed_hydronyms import (
    HYDRO_SKIP_RELS,
    apply_harvest,
    drop_incoming_rivers,
    harvest,
    load_main_query,
    load_parent_index,
    load_rows_from_json,
    main,
    map_hydronym,
    p31_from_query,
    queries_for_p31,
    too_large_or_timeout,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "hydronyms_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "hydronyms-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _copy_csv(src: Path, dest: Path) -> None:
    header, rows = read_csv(src)
    write_csv(dest, header, rows)


def _volga(**kwargs: str) -> dict[str, str]:
    row = _place(
        id="wd:Q626",
        id_scheme="wikidata",
        type_id="potamonym",
        name_ru="Волга",
        name_en="Volga",
        wd="Q626",
        geonames="472776",
        status="active",
        source_id="wikidata",
        updated_at="2026-09-09",
        notes="keep notes",
    )
    row.update(kwargs)
    return row


def test_sparql_hydronyms_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    assert "Q23397" in text
    assert "Q4022" in text
    assert "Q159" in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    values = text.split("VALUES ?type", 1)[1].split("}", 1)[0]
    assert "Q165" not in values
    assert "FILTER(?type != wd:Q4022" in text
    assert "ru.wikipedia.org" in text
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000


def test_load_main_query_hydronym_one_select_rivers_last() -> None:
    query = load_main_query(SPARQL)
    types = p31_from_query(query)
    assert types == ["Q23397", "Q4022"]
    split = queries_for_p31(query)
    assert [qid for qid, _typed in split] == types
    assert types[-1] == "Q4022"
    assert "wd:Q23397" in query and "wd:Q4022" in query
    assert query.count("SELECT") == 1
    for qid, typed in split:
        assert f"VALUES ?type {{ wd:{qid} }}" in typed
        assert "wd:Q23397 wd:Q4022" not in typed
        assert "FILTER(?type != wd:Q4022" in typed


def test_hydro_skip_rels_frozen_without_self() -> None:
    rels = {str(path).replace("\\", "/") for path in HYDRO_SKIP_RELS}
    assert "data/curated/hydronyms-major.csv" not in rels
    assert "data/curated/oronyms-major.csv" in rels
    assert "data/curated/cities-major.csv" in rels
    assert "data/curated/regions.csv" in rels
    assert "data/curated/villages.csv" in rels


def test_map_hydronym_yo_oktmo_and_stable_id() -> None:
    rec = {
        "qid": "Q90007007",
        "ru": "Зелёное озеро",
        "en": "Zelyonoye Lake",
        "lat": "54.1",
        "lon": "39.2",
        "gn": "1",
        "oktmo": "46 000 000",
        "p31": {"Q23397"},
    }
    row = map_hydronym(rec, ("iso:RU-MOS", "RU-MOS"), "2026-09-15")
    assert row["id"] == "wd:Q90007007"
    assert row["id_scheme"] == "wikidata"
    assert row["type_id"] == "limnonym"
    assert row["name_ru"] == "Зеленое озеро"
    assert row["name_yo"] == "Зелёное озеро"
    assert row["parent_id"] == "iso:RU-MOS"
    assert row["oktmo"] == "46000000"
    assert row["source_id"] == "wikidata"


def test_drop_incoming_rivers_keeps_lakes() -> None:
    records = {
        "Q1": {"p31": {"Q4022"}, "ru": "река"},
        "Q2": {"p31": {"Q23397"}, "ru": "озеро"},
        "Q3": {"p31": {"Q4022", "Q23397"}, "ru": "оба"},
    }
    kept = drop_incoming_rivers(records)
    assert "Q1" not in kept
    assert "Q2" in kept
    assert "Q3" in kept
    assert too_large_or_timeout(SeedError("SPARQL HTTP 500: timeout"))
    assert too_large_or_timeout(SeedError("hydronyms-major.csv 11 байт > 10 (не вендорить дамп)"))
    assert not too_large_or_timeout(SeedError("SPARQL HTTP 400: syntax"))


def test_apply_harvest_clears_bogus_adygea_keeps_volga_don() -> None:
    records = {
        "Q9100101": {
            "qid": "Q9100101",
            "ru": "Озеро без родителя",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": set(),
            "iso": set(),
            "p31": {"Q23397"},
            "replaced": set(),
            "dissolved": "",
        },
        "Q9100102": {
            "qid": "Q9100102",
            "ru": "Река в Татарстане",
            "en": "",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": set(),
            "iso": {"RU-TA"},
            "p31": {"Q4022"},
            "replaced": set(),
            "dissolved": "",
        },
        "Q626": {
            "qid": "Q626",
            "ru": "Волга",
            "en": "Volga",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": set(),
            "iso": set(),
            "p31": {"Q4022"},
            "replaced": set(),
            "dissolved": "",
        },
        "Q1229": {
            "qid": "Q1229",
            "ru": "Дон",
            "en": "Don",
            "lat": "",
            "lon": "",
            "gn": "",
            "oktmo": "",
            "located": set(),
            "iso": {"RU-AD"},
            "p31": {"Q4022"},
            "replaced": set(),
            "dissolved": "",
        },
    }
    index = load_parent_index(ROOT)
    existing = [
        _place(
            id="wd:Q9100101",
            id_scheme="wikidata",
            type_id="limnonym",
            name_ru="Озеро без родителя",
            wd="Q9100101",
            parent_id="iso:RU-AD",
            admin1="RU-AD",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-17",
            notes="keep notes",
        ),
        _place(
            id="wd:Q9100102",
            id_scheme="wikidata",
            type_id="potamonym",
            name_ru="Река в Татарстане",
            wd="Q9100102",
            parent_id="iso:RU-AD",
            admin1="RU-AD",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-17",
        ),
        _place(
            id="wd:Q626",
            id_scheme="wikidata",
            type_id="potamonym",
            name_ru="Волга",
            wd="Q626",
            parent_id="iso:RU-CU",
            admin1="RU-CU",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-09",
            notes="keep notes",
        ),
        _place(
            id="wd:Q1229",
            id_scheme="wikidata",
            type_id="potamonym",
            name_ru="Дон",
            wd="Q1229",
            parent_id="iso:RU-LIP",
            admin1="RU-LIP",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-09",
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
    assert by_id["wd:Q9100101"]["parent_id"] == ""
    assert by_id["wd:Q9100101"]["admin1"] == ""
    assert by_id["wd:Q9100101"]["notes"] == "keep notes"
    assert by_id["wd:Q9100102"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q9100102"]["admin1"] == "RU-TA"
    assert by_id["wd:Q626"]["parent_id"] == "iso:RU-CU"
    assert by_id["wd:Q626"]["admin1"] == "RU-CU"
    assert by_id["wd:Q626"]["notes"] == "keep notes"
    assert by_id["wd:Q1229"]["parent_id"] == "iso:RU-LIP"
    assert by_id["wd:Q1229"]["admin1"] == "RU-LIP"
    assert counts.inserted == 0
    assert len(places) == 4


def test_apply_harvest_empty_parent_keeps_gold_skips_sea() -> None:
    rows = load_rows_from_json(FIXTURE)
    records = merge_bindings(
        rows, extra_scalars=("oktmo", "dissolved"), extra_qid_sets=("replaced", "p31")
    )
    index = load_parent_index(ROOT)
    existing = [
        _volga(),
        _place(
            id="wd:Q1229",
            id_scheme="wikidata",
            type_id="potamonym",
            name_ru="Дон",
            name_en="Don",
            wd="Q1229",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-09",
        ),
        _place(
            id="wd:Q166",
            id_scheme="wikidata",
            type_id="hydronym",
            name_ru="Черное море",
            name_yo="Чёрное море",
            name_en="Black Sea",
            wd="Q166",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-09",
        ),
        _place(
            id="wd:Q90007006",
            id_scheme="wikidata",
            type_id="potamonym",
            name_ru="Старая река",
            wd="Q90007006",
            status="active",
            source_id="wikidata",
            updated_at="2026-09-11",
            notes="keep notes",
        ),
    ]
    skip_map = {"Q90007004": "cities-major"}
    known = {f"wd:{qid}" for qid in records}
    known.update(row["id"] for row in existing if row.get("id"))
    gold = {
        "id": "wd:Q626",
        "type_code": "potamonym",
        "lemma": "Волга",
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
    assert by_id["wd:Q90007001"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q90007001"]["type_id"] == "limnonym"
    assert by_id["wd:Q90007002"]["type_id"] == "potamonym"
    assert by_id["wd:Q90007002"]["parent_id"] == ""
    assert "wd:Q90007003" not in by_id
    assert counts.skipped_other >= 1
    assert "wd:Q90007004" not in by_id
    assert counts.skipped_overlap >= 1
    assert "wd:Q90007005" not in by_id
    assert "wd:Q90007008" not in by_id
    volga = by_id["wd:Q626"]
    assert volga["notes"] == "keep notes"
    assert volga["type_id"] == "potamonym"
    assert by_id["wd:Q166"]["type_id"] == "hydronym"
    abolished = by_id["wd:Q90007006"]
    assert abolished["status"] == "deprecated"
    assert abolished["replaced_by"] == "wd:Q90007001"
    assert abolished["notes"] == "keep notes"
    assert by_id["wd:Q90007007"]["name_ru"] == "Зеленое озеро"
    assert by_id["wd:Q90007007"]["type_id"] == "limnonym"
    stubs = [row for row in decls if row["id"] == "wd:Q90007001"]
    assert len(stubs) == 1
    assert stubs[0]["review"] == "needs_review"
    assert stubs[0]["type_code"] == "limnonym"
    assert stubs[0]["source"] == "wikidata"
    gold_rows = [row for row in decls if row["id"] == "wd:Q626"]
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
                id="wd:Q90007004",
                wd="Q90007004",
                name_ru="Перекрытие с городом",
                type_id="city",
            )
        ],
    )
    write_csv(
        curated / "hydronyms-major.csv",
        PLACES_HEADER,
        [
            _volga(),
            _place(
                id="wd:Q1229",
                id_scheme="wikidata",
                type_id="potamonym",
                name_ru="Дон",
                wd="Q1229",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-09",
            ),
            _place(
                id="wd:Q166",
                id_scheme="wikidata",
                type_id="hydronym",
                name_ru="Черное море",
                name_yo="Чёрное море",
                wd="Q166",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-09",
            ),
            _place(
                id="wd:Q90007006",
                id_scheme="wikidata",
                type_id="potamonym",
                name_ru="Старая река",
                wd="Q90007006",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-11",
                notes="keep notes",
            ),
        ],
    )
    write_csv(decl / "hydronyms-major.csv", DECLENSIONS_HEADER, [])
    (raw / "hydronyms-ru.sparql").write_text(
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
    assert "bytes_places=" in out.out
    assert "bytes_decl=" in out.out
    assert "skip overlap wd:Q90007004 table=cities-major" in out.err
    _header, rows = read_csv(curated / "hydronyms-major.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["wd:Q90007001"]["parent_id"] == "iso:RU-TA"
    assert by_id["wd:Q90007001"]["type_id"] == "limnonym"
    assert by_id["wd:Q90007002"]["parent_id"] == ""
    assert "wd:Q90007003" not in by_id
    assert "wd:Q90007004" not in by_id
    assert "wd:Q90007005" not in by_id
    assert "wd:Q90007008" not in by_id
    assert by_id["wd:Q626"]["notes"] == "keep notes"
    assert by_id["wd:Q166"]["type_id"] == "hydronym"
    assert by_id["wd:Q90007006"]["status"] == "deprecated"
    assert by_id["wd:Q90007007"]["type_id"] == "limnonym"
    assert len(read_csv(ROOT / "data/curated/hydronyms-major.csv")[1]) >= 500


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
    assert any(row["id"] == "wd:Q626" for row in places)
    assert any(row["id"] == "wd:Q1229" for row in places)
    assert any(row["id"] == "wd:Q90007001" for row in places)
    assert any(row["id"] == "wd:Q90007002" for row in places)
    assert not any(row["id"] == "wd:Q90007008" for row in places)
    assert len(read_csv(ROOT / "data/curated/hydronyms-major.csv")[1]) >= 500


def test_harvest_live_one_select(monkeypatch, tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(curated / "cities-major.csv", PLACES_HEADER, [])
    write_csv(curated / "hydronyms-major.csv", PLACES_HEADER, [_volga()])
    write_csv(decl / "hydronyms-major.csv", DECLENSIONS_HEADER, [])
    (raw / "hydronyms-ru.sparql").write_text(
        SPARQL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    calls: list[str] = []

    def fake_sparql(_session, query: str, timeout: int = 90):
        calls.append(query)
        assert "wd:Q23397" in query
        assert "wd:Q4022" in query
        return [
            {
                "item": "http://www.wikidata.org/entity/Q5513",
                "type": "http://www.wikidata.org/entity/Q23397",
                "ru": "Байкал",
                "en": "Lake Baikal",
            }
        ]

    monkeypatch.setattr("scripts.seed_hydronyms.sparql_csv", fake_sparql)
    places, _decls, _counts, _ph, _dh = harvest(
        root=tmp_path,
        today="2026-09-15",
        from_json=None,
        from_csv=None,
        hop=False,
        hop_batch=80,
        session=object(),  # type: ignore[arg-type]
    )
    assert len(calls) == 1
    assert any(row["id"] == "wd:Q5513" and row["type_id"] == "limnonym" for row in places)
    assert any(row["id"] == "wd:Q626" for row in places)


def test_harvest_timeout_drops_incoming_rivers(monkeypatch, tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(curated / "cities-major.csv", PLACES_HEADER, [])
    write_csv(
        curated / "hydronyms-major.csv",
        PLACES_HEADER,
        [
            _volga(),
            _place(
                id="wd:Q166",
                id_scheme="wikidata",
                type_id="hydronym",
                name_ru="Черное море",
                wd="Q166",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-09",
            ),
        ],
    )
    write_csv(decl / "hydronyms-major.csv", DECLENSIONS_HEADER, [])
    (raw / "hydronyms-ru.sparql").write_text(
        SPARQL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    calls: list[str] = []

    def fake_sparql(_session, query: str, timeout: int = 90):
        calls.append(query)
        if "Q4022" in p31_from_query(query):
            raise SeedError("SPARQL HTTP 500: timeout")
        return [
            {
                "item": "http://www.wikidata.org/entity/Q5513",
                "type": "http://www.wikidata.org/entity/Q23397",
                "ru": "Байкал",
                "en": "Lake Baikal",
            },
            {
                "item": "http://www.wikidata.org/entity/Q90007002",
                "type": "http://www.wikidata.org/entity/Q4022",
                "ru": "Не должна войти",
            },
        ]

    monkeypatch.setattr("scripts.seed_hydronyms.sparql_csv", fake_sparql)
    places, _decls, _counts, _ph, _dh = harvest(
        root=tmp_path,
        today="2026-09-15",
        from_json=None,
        from_csv=None,
        hop=False,
        hop_batch=80,
        session=object(),  # type: ignore[arg-type]
    )
    assert len(calls) == 2
    assert p31_from_query(calls[0]) == ["Q23397", "Q4022"]
    assert p31_from_query(calls[1]) == ["Q23397"]
    by_id = {row["id"]: row for row in places}
    assert "wd:Q90007002" not in by_id
    assert by_id["wd:Q5513"]["type_id"] == "limnonym"
    assert by_id["wd:Q626"]["name_ru"] == "Волга"
    assert by_id["wd:Q166"]["type_id"] == "hydronym"


def test_dump_too_large_drops_incoming_rivers(monkeypatch, tmp_path: Path) -> None:
    curated = tmp_path / "data" / "curated"
    decl = tmp_path / "data" / "declensions"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    decl.mkdir(parents=True)
    raw.mkdir(parents=True)
    _copy_csv(ROOT / "data/curated/regions.csv", curated / "regions.csv")
    write_csv(curated / "cities-major.csv", PLACES_HEADER, [])
    write_csv(
        curated / "hydronyms-major.csv",
        PLACES_HEADER,
        [
            _volga(),
            _place(
                id="wd:Q166",
                id_scheme="wikidata",
                type_id="hydronym",
                name_ru="Черное море",
                wd="Q166",
                status="active",
                source_id="wikidata",
                updated_at="2026-09-09",
            ),
        ],
    )
    write_csv(decl / "hydronyms-major.csv", DECLENSIONS_HEADER, [])
    (raw / "hydronyms-ru.sparql").write_text(
        SPARQL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    from scripts.lib.harvest import dump_csv_bytes_or_raise as real_dump

    seen = {"n": 0}

    def fake_dump(header, rows, label):
        seen["n"] += 1
        if seen["n"] == 1 and label == "hydronyms-major.csv":
            raise SeedError(
                f"{label} 99999999 байт > 10485760 (не вендорить дамп)"
            )
        return real_dump(header, rows, label)

    monkeypatch.setattr("scripts.seed_hydronyms.dump_csv_bytes_or_raise", fake_dump)
    places, _decls, _counts, _ph, _dh = harvest(
        root=tmp_path,
        today="2026-09-15",
        from_json=FIXTURE,
        from_csv=None,
        hop=False,
        hop_batch=80,
        session=None,
    )
    by_id = {row["id"]: row for row in places}
    assert "wd:Q90007002" not in by_id
    assert by_id["wd:Q90007001"]["type_id"] == "limnonym"
    assert by_id["wd:Q626"]["name_ru"] == "Волга"
    assert by_id["wd:Q166"]["type_id"] == "hydronym"
    assert seen["n"] >= 3


def test_canon_hydronyms_harvested() -> None:
    _header, rows = read_csv(ROOT / "data/curated/hydronyms-major.csv")
    assert len(rows) >= 500
    assert any(row["id"] == "wd:Q626" and row["name_ru"] == "Волга" for row in rows)
    assert any(row["id"] == "wd:Q1229" and row["name_ru"] == "Дон" for row in rows)
    assert any(row["id"] == "wd:Q5513" and row["type_id"] == "limnonym" for row in rows)
    assert any(row["id"] == "wd:Q166" and row["type_id"] == "hydronym" for row in rows)
    _dh, decls = read_csv(ROOT / "data/declensions/hydronyms-major.csv")
    gold = {(row["id"], row["lemma"]) for row in decls if row["review"] == "gold"}
    assert ("wd:Q626", "Волга") in gold
    assert ("wd:Q1229", "Дон") in gold
