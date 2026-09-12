from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import jsonschema
import yaml

from scripts.seed_hodonyms import load_main_query, p31_from_query

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
    assert payload["filter"]["hodonym_p31"] == [
        "Q79007",
        "Q54114",
        "Q628179",
        "Q1251403",
        "Q537127",
    ]
    sparql = ROOT / "data" / "raw" / "wikidata" / "hodonyms-ru.sparql"
    assert payload["filter"]["hodonym_p31"] == p31_from_query(load_main_query(sparql))
    assert "seed_hodonyms.py" in payload["notes"]
    assert "Q628179" in payload["notes"]
    assert "polygon" not in payload["fields"].values()
    assert "geojson" not in {v.casefold() for v in payload["fields"].values()}
    assert "без полигонов" in payload["notes"] or "dec-geo-001" in notes
    assert "dec-geo-001" in notes
    assert "sparql" in notes
    assert "dump" in notes or "дамп" in payload["notes"].casefold()


def test_geonames_notes_mention_no_insert() -> None:
    payload = _load_yaml(MAPPINGS_DIR / "geonames.yaml")
    notes = payload["notes"].lower()
    assert payload["source_id"] == "geonames-ru"
    assert payload["stable_id"] == "gn:{geonameId}"
    assert payload["delete_policy"] == "deprecate"
    assert "no-insert" in notes or "never insert" in notes
    assert "geonames" in notes
