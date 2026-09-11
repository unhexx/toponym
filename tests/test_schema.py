from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema"
CATALOG_SCHEMA = SCHEMA_DIR / "catalog.schema.json"
TYPES_CSV = ROOT / "data" / "curated" / "types.csv"
TYPES_SCHEMA = SCHEMA_DIR / "table" / "types.schema.json"
PLACES_SCHEMA = SCHEMA_DIR / "table" / "places.schema.json"
AGENCIES_SCHEMA = SCHEMA_DIR / "table" / "agencies.schema.json"
DECL_SCHEMA = SCHEMA_DIR / "table" / "declensions.schema.json"
DATAPACKAGE = ROOT / "datapackage.json"
DETECTOR_KINDS = {"http_head", "http_dated", "github_commits", "page_fingerprint", "none"}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def test_schema_files_are_json() -> None:
    for path in SCHEMA_DIR.rglob("*.json"):
        payload = _load_json(path)
        assert isinstance(payload, dict), path


def test_catalog_yaml_matches_schema() -> None:
    schema = _load_json(CATALOG_SCHEMA)
    catalog = _load_yaml(ROOT / "data" / "sources" / "catalog.yaml")
    jsonschema.Draft202012Validator(schema).validate(catalog)
    for source in catalog["sources"]:
        assert source["detector"]["kind"] in DETECTOR_KINDS


def test_catalog_fixture_valid() -> None:
    schema = _load_json(CATALOG_SCHEMA)
    catalog = _load_yaml(ROOT / "tests" / "fixtures" / "catalog_valid.yaml")
    jsonschema.Draft202012Validator(schema).validate(catalog)


def test_catalog_fixture_invalid_missing_id() -> None:
    schema = _load_json(CATALOG_SCHEMA)
    catalog = _load_yaml(ROOT / "tests" / "fixtures" / "catalog_invalid.yaml")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(catalog)


def test_types_csv_header_matches_schema() -> None:
    schema_fields = [f["name"] for f in _load_json(TYPES_SCHEMA)["fields"]]
    with TYPES_CSV.open(encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == schema_fields


def test_places_and_agencies_share_header() -> None:
    places = [f["name"] for f in _load_json(PLACES_SCHEMA)["fields"]]
    agencies = [f["name"] for f in _load_json(AGENCIES_SCHEMA)["fields"]]
    assert places == agencies
    assert places[0] == "id"
    assert "name_yo" in places
    assert "status" in places


def test_declensions_header_frozen() -> None:
    expected = [
        "id",
        "type_code",
        "lemma",
        "yo",
        "gender",
        "paradigm",
        "declinable",
        "nom",
        "gen",
        "dat",
        "acc",
        "ins",
        "pre",
        "loc2",
        "review",
        "source",
    ]
    schema = _load_json(DECL_SCHEMA)
    assert [f["name"] for f in schema["fields"]] == expected
    assert schema.get("primaryKey") == ["id", "lemma"]
    id_field = next(field for field in schema["fields"] if field["name"] == "id")
    assert id_field.get("constraints", {}).get("unique") is not True


def test_datapackage_schema_paths_exist() -> None:
    pkg = _load_json(DATAPACKAGE)
    assert pkg["resources"], "datapackage has no resources"
    for resource in pkg["resources"]:
        schema_path = ROOT / resource["schema"]
        assert schema_path.is_file(), resource["name"]
        assert resource["dialect"]["delimiter"] == ","
        assert resource["encoding"] == "utf-8"


def test_mapping_schema_rejects_unknown_delete_policy() -> None:
    schema = _load_json(SCHEMA_DIR / "mapping.schema.json")
    bad = {
        "source_id": "geonames-ru",
        "stable_id": "gn:{geonameId}",
        "fields": {"name": "name"},
        "delete_policy": "erase",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(bad)
