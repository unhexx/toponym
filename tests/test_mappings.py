from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import jsonschema
import yaml

from scripts.lib.harvest import load_main_query as load_harvest_query
from scripts.seed_hodonyms import load_main_query, p31_from_query
from scripts.seed_microtoponyms import load_main_query as load_micro_query
from scripts.seed_municipalities import load_main_query as load_mun_query

ROOT = Path(__file__).resolve().parents[1]
MAPPINGS_DIR = ROOT / "data" / "mappings"
MAPPING_SCHEMA = ROOT / "schema" / "mapping.schema.json"
CATALOG = ROOT / "data" / "sources" / "catalog.yaml"
DELETE_POLICIES = {"deprecate", "ignore", "pointer"}
EXPECTED_FILES = (
    "geonames.yaml",
    "gkgn.yaml",
    "fias-pointer.yaml",
    "hflabs-region.yaml",
    "hflabs-city.yaml",
    "ukase-326.yaml",
    "wikidata.yaml",
)


def _stringify_dates(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _stringify_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify_dates(v) for v in value]
    return value


def _load_yaml(path: Path) -> dict:
    return _stringify_dates(yaml.safe_load(path.read_text(encoding="utf-8")))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping_paths() -> list[Path]:
    return [MAPPINGS_DIR / name for name in EXPECTED_FILES]


def test_expected_mapping_files_exist() -> None:
    for path in _mapping_paths():
        assert path.is_file(), path


def test_each_mapping_validates_against_schema() -> None:
    schema = _load_json(MAPPING_SCHEMA)
    validator = jsonschema.Draft202012Validator(schema)
    for path in _mapping_paths():
        payload = _load_yaml(path)
        errors = list(validator.iter_errors(payload))
        assert not errors, f"{path.name}: {errors[0].message}"


def test_delete_policy_in_enum() -> None:
    for path in _mapping_paths():
        payload = _load_yaml(path)
        assert payload["delete_policy"] in DELETE_POLICIES, path.name
        assert "pointer" not in payload or payload["delete_policy"] == "pointer"
        assert payload.get("pointer") is not True


def test_source_id_in_catalog() -> None:
    catalog = _load_yaml(CATALOG)
    catalog_ids = {source["id"] for source in catalog["sources"]}
    for path in _mapping_paths():
        payload = _load_yaml(path)
        assert payload["source_id"] in catalog_ids, path.name


def test_pointer_sources_use_delete_policy_pointer() -> None:
    for name in (
        "fias-pointer.yaml",
        "hflabs-region.yaml",
        "hflabs-city.yaml",
        "wikidata.yaml",
    ):
        payload = _load_yaml(MAPPINGS_DIR / name)
        assert payload["delete_policy"] == "pointer", name


def test_hflabs_city_mapping_is_fias_join_pointer() -> None:
    payload = _load_yaml(MAPPINGS_DIR / "hflabs-city.yaml")
    notes = payload["notes"].casefold()
    assert payload["source_id"] == "hflabs-city"
    assert payload["stable_id"] == "fias:{fias_id}"
    assert payload["delete_policy"] == "pointer"
    assert payload["fields"]["fias_id"] == "fias"
    assert payload["fields"]["oktmo"] == "oktmo"
    assert "name_ru" not in payload["fields"].values()
    assert "city" not in payload["fields"]
    assert "cc-by-sa" in notes or "sharealike" in notes or "не копировать" in payload["notes"]
    assert "dec-hflabs-001" in notes


def test_wikidata_mapping_points_and_no_sparql_dump() -> None:
    payload = _load_yaml(MAPPINGS_DIR / "wikidata.yaml")
    notes = payload["notes"].casefold()
    assert payload["source_id"] == "wikidata"
    assert payload["stable_id"] == "wd:{qid}"
    assert payload["delete_policy"] == "pointer"
    assert payload["fields"]["qid"] == "wd"
    assert payload["fields"]["label_ru"] == "name_ru"
    assert payload["fields"]["label_en"] == "name_en"
    assert payload["fields"]["P625_lat"] == "lat"
    assert payload["fields"]["P625_lon"] == "lon"
    assert payload["filter"]["known_ids_only"] is True
    assert payload["class_map"]["Q79007"] == "hodonym"
    assert payload["class_map"]["Q54114"] == "hodonym"
    assert payload["class_map"]["Q628179"] == "hodonym"
    assert payload["class_map"]["Q1251403"] == "hodonym"
    assert payload["class_map"]["Q537127"] == "hodonym"
    assert payload["class_map"]["Q174782"] == "agoronym"
    assert payload["class_map"]["Q7930989"] == "city"
    assert payload["class_map"]["Q15078955"] == "village"
    assert payload["class_map"]["Q5084"] == "village"
    assert payload["class_map"]["Q728937"] == "dromonym"
    assert payload["class_map"]["Q4022"] == "potamonym"
    assert payload["class_map"]["Q23397"] == "limnonym"
    assert payload["class_map"]["Q165"] == "hydronym"
    assert payload["class_map"]["Q8502"] == "oronym"
    assert payload["class_map"]["Q46831"] == "oronym"
    assert payload["class_map"]["Q8072"] == "oronym"
    assert payload["class_map"]["Q23442"] == "insulonym"
    assert payload["class_map"]["Q34763"] == "insulonym"
    assert payload["class_map"]["Q13626398"] == "municipality"
    assert payload["class_map"]["Q3350075"] == "municipality"
    assert payload["class_map"]["Q2198484"] == "municipality"
    assert payload["class_map"]["Q60849925"] == "municipality"
    assert payload["class_map"]["Q2661988"] == "municipality"
    assert payload["class_map"]["Q634099"] == "municipality"
    assert payload["class_map"]["Q27587207"] == "municipality"
    assert payload["class_map"]["Q1434274"] == "microtoponym"
    assert payload["class_map"]["Q125505344"] == "microtoponym"
    assert payload["class_map"]["Q1361400"] == "microtoponym"
    assert payload["class_map"]["Q188869"] == "microtoponym"
    assert payload["class_map"]["Q35509"] == "microtoponym"
    assert payload["class_map"]["Q22698"] == "microtoponym"
    assert payload["filter"]["hodonym_p31"] == [
        "Q79007",
        "Q54114",
        "Q628179",
        "Q1251403",
        "Q537127",
    ]
    assert payload["filter"]["municipality_p31"] == [
        "Q13626398",
        "Q3350075",
        "Q2198484",
        "Q60849925",
        "Q27587207",
        "Q2661988",
        "Q634099",
    ]
    assert payload["filter"]["microtoponym_p31"] == [
        "Q1434274",
        "Q125505344",
        "Q1361400",
        "Q188869",
        "Q35509",
        "Q22698",
    ]
    assert payload["filter"]["city_p31"] == ["Q7930989"]
    assert payload["filter"]["village_p31"] == ["Q15078955", "Q532"]
    assert payload["filter"]["agoronym_p31"] == ["Q174782"]
    assert payload["filter"]["dromonym_p31"] == ["Q34442", "Q728937"]
    assert payload["filter"]["hydronym_p31"] == ["Q23397", "Q4022"]
    assert payload["filter"]["oronym_p31"] == [
        "Q8502",
        "Q46831",
        "Q8072",
        "Q23442",
        "Q34763",
    ]
    sparql = ROOT / "data" / "raw" / "wikidata" / "hodonyms-ru.sparql"
    assert payload["filter"]["hodonym_p31"] == p31_from_query(load_main_query(sparql))
    mun_sparql = ROOT / "data" / "raw" / "wikidata" / "municipalities-ru.sparql"
    assert payload["filter"]["municipality_p31"] == p31_from_query(load_mun_query(mun_sparql))
    micro_sparql = ROOT / "data" / "raw" / "wikidata" / "microtoponyms-ru.sparql"
    assert payload["filter"]["microtoponym_p31"] == p31_from_query(
        load_micro_query(micro_sparql)
    )
    assert "seed_hodonyms.py" in payload["notes"]
    assert "seed_municipalities.py" in payload["notes"]
    assert "sync.py" in payload["notes"]
    assert "VALUES" in payload["notes"] or "values" in notes
    assert "Q628179" in payload["notes"]
    assert "polygon" not in payload["fields"].values()
    assert "geojson" not in {v.casefold() for v in payload["fields"].values()}
    assert "без полигонов" in payload["notes"] or "dec-geo-001" in notes
    assert "dec-geo-001" in notes
    assert "sparql" in notes
    assert "dump" in notes or "дамп" in payload["notes"].casefold()


def test_wikidata_coverage_sparql_pointers_match_p31_filters() -> None:
    payload = _load_yaml(MAPPINGS_DIR / "wikidata.yaml")
    raw = ROOT / "data" / "raw" / "wikidata"
    skeleton = (
        "VALUES ?type",
        "Q159",
        "?item rdfs:label ?ru",
        "P625",
        "P1566",
        "P764",
        "P131",
        "P576",
        "P1366",
    )
    specs = (
        ("cities-ru.sparql", "city_p31", None),
        ("villages-ru.sparql", "village_p31", None),
        ("agoronyms-ru.sparql", "agoronym_p31", None),
        ("dromonyms-ru.sparql", "dromonym_p31", "Q728937"),
        ("hydronyms-ru.sparql", "hydronym_p31", "Q4022"),
        ("oronyms-ru.sparql", "oronym_p31", None),
        ("foiv-ru.sparql", "foiv_p31", None),
    )
    for name, filter_key, guard_qid in specs:
        path = raw / name
        text = path.read_text(encoding="utf-8")
        assert path.stat().st_size < 10_000, name
        assert "не вендор" in text.casefold() or "do not vendor" in text.casefold(), name
        query = load_harvest_query(path)
        for needle in skeleton:
            assert needle in query, f"{name}: {needle}"
        assert payload["filter"][filter_key] == p31_from_query(query), name
        if guard_qid is None:
            continue
        assert f"FILTER(?type != wd:{guard_qid}" in query, name
        assert "schema:isPartOf <https://ru.wikipedia.org/>" in query, name
    villages = load_harvest_query(raw / "villages-ru.sparql")
    assert "Q5084" not in villages
    assert "Q5084" in (raw / "villages-ru.sparql").read_text(encoding="utf-8")
    hydronyms = load_harvest_query(raw / "hydronyms-ru.sparql")
    assert "Q165" not in p31_from_query(hydronyms)


def test_geonames_notes_mention_no_insert() -> None:
    payload = _load_yaml(MAPPINGS_DIR / "geonames.yaml")
    notes = payload["notes"].lower()
    assert payload["source_id"] == "geonames-ru"
    assert payload["stable_id"] == "gn:{geonameId}"
    assert payload["delete_policy"] == "deprecate"
    assert "no-insert" in notes or "never insert" in notes
    assert "geonames" in notes
