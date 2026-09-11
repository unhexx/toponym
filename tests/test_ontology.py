from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
ONT_PATH = ROOT / "ontology" / "ontology.json"
ONT_SCHEMA = ROOT / "ontology" / "ontology.schema.json"
CATALOG = ROOT / "data" / "sources" / "catalog.yaml"
REQUIRED_IDS = {
    "PRJ-TOPONYM",
    "DEC-REG-001",
    "ART-CATALOG",
    "ART-DATAPACKAGE",
    "ART-SCHEMA",
    "REG-PLACES",
    "REG-AGENCIES",
    "REG-DECLENSIONS",
    "REG-TYPES",
    "MAP-GN-CANON",
    "MAP-GKGN",
    "MAP-FIAS-POINTER",
    "MAP-HFLABS-REGION",
    "MAP-UKASE-326",
    "CHK-DETECTOR",
    "RSK-FIAS-VENDOR",
    "RSK-CCBYSA-CURATED",
    "RSK-EMPTY-COMMIT",
    "LSN-SEEDS-MISSING",
    "DEC-SERVE-001",
    "ART-SERVE",
    "ART-COMPOSE",
    "RSK-PUBLIC-BIND",
    "RSK-PORT-COLLISION",
    "DEC-GN-001",
    "RSK-GN-INSERT",
    "DEC-DECL-001",
    "DEC-DECL-002",
    "DEC-TAX-001",
    "DEC-SERVE-002",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ontology_parses_and_matches_schema() -> None:
    payload = _load_json(ONT_PATH)
    schema = _load_json(ONT_SCHEMA)
    assert payload["schema"] == "outpost-ontology/v1"
    assert payload["project"]["id"] == "PRJ-TOPONYM"
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_decision_dec_reg_001() -> None:
    payload = _load_json(ONT_PATH)
    by_id = {row["id"]: row for row in payload["entities"]}
    decision = by_id["DEC-REG-001"]
    assert decision["type"] == "Decision"
    assert decision["status"] == "accepted"


def test_source_count_matches_catalog() -> None:
    payload = _load_json(ONT_PATH)
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    catalog_ids = [src["id"] for src in catalog["sources"]]
    sources = [row for row in payload["entities"] if row["type"] == "Source"]
    assert len(sources) == len(catalog_ids)
    expected = {f"SRC-{sid.upper()}" for sid in catalog_ids}
    got = {row["id"] for row in sources}
    assert got == expected
    catalog_on_entities = {row["catalog_id"] for row in sources}
    assert catalog_on_entities == set(catalog_ids)


def test_required_entities_present() -> None:
    payload = _load_json(ONT_PATH)
    by_id = {row["id"]: row for row in payload["entities"]}
    missing = REQUIRED_IDS - set(by_id)
    assert not missing, missing
    assert by_id["RSK-FIAS-VENDOR"]["type"] == "Risk"
    assert by_id["RSK-CCBYSA-CURATED"]["type"] == "Risk"
    assert by_id["RSK-EMPTY-COMMIT"]["type"] == "Risk"
    assert by_id["LSN-SEEDS-MISSING"]["type"] == "Lesson"
    assert by_id["PRJ-TOPONYM"]["type"] == "Project"
    assert by_id["DEC-SERVE-001"]["type"] == "Decision"
    assert by_id["DEC-SERVE-001"]["status"] == "accepted"
    assert by_id["ART-SERVE"]["type"] == "Artifact"
    assert by_id["ART-COMPOSE"]["type"] == "Artifact"
    assert by_id["RSK-PUBLIC-BIND"]["type"] == "Risk"
    assert by_id["RSK-PORT-COLLISION"]["type"] == "Risk"
    assert by_id["DEC-GN-001"]["type"] == "Decision"
    assert by_id["DEC-GN-001"]["status"] == "accepted"
    summary = by_id["DEC-GN-001"]["summary"]
    assert "gn:" in summary
    assert "skipped_unmapped" in summary
    assert by_id["RSK-GN-INSERT"]["type"] == "Risk"
    assert by_id["DEC-DECL-001"]["type"] == "Decision"
    assert by_id["DEC-DECL-001"]["status"] == "accepted"
    assert "queue.csv" in by_id["DEC-DECL-001"]["summary"]
    assert by_id["DEC-DECL-002"]["type"] == "Decision"
    assert by_id["DEC-DECL-002"]["status"] == "accepted"
    assert "(id, lemma)" in by_id["DEC-DECL-002"]["title"]
    assert by_id["DEC-TAX-001"]["type"] == "Decision"
    assert by_id["DEC-TAX-001"]["status"] == "accepted"
    summary = by_id["DEC-TAX-001"]["summary"]
    assert "toponym" in summary and "oikonym" in summary and "hydronym" in summary
    assert by_id["DEC-SERVE-002"]["type"] == "Decision"
    assert by_id["DEC-SERVE-002"]["status"] == "accepted"
    assert "0.0.0.0" in by_id["DEC-SERVE-002"]["summary"]
