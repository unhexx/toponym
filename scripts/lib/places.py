from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
PLACES_SCHEMA = "places.schema.json"
AGENCIES_SCHEMA = "agencies.schema.json"


def _schema_name(schema: object) -> str:
    if not isinstance(schema, str):
        return ""
    return Path(schema).name


def _load_resources(datapackage: Path) -> list[dict[str, Any]]:
    payload = json.loads(datapackage.read_text(encoding="utf-8"))
    resources = payload.get("resources") or []
    return [res for res in resources if isinstance(res, dict)]


def _paths_for_schema(resources: list[dict[str, Any]], schema_name: str) -> list[str]:
    paths: list[str] = []
    for res in resources:
        if _schema_name(res.get("schema")) != schema_name:
            continue
        path = res.get("path") or ""
        if path:
            paths.append(str(path))
    return paths


def load_place_relpaths(root: Path | None = None) -> list[str]:
    datapackage = (root or _ROOT) / "datapackage.json"
    return _paths_for_schema(_load_resources(datapackage), PLACES_SCHEMA)


def load_index_relpaths(root: Path | None = None) -> list[str]:
    datapackage = (root or _ROOT) / "datapackage.json"
    resources = _load_resources(datapackage)
    return _paths_for_schema(resources, PLACES_SCHEMA) + _paths_for_schema(
        resources, AGENCIES_SCHEMA
    )


PLACE_RELPATHS = load_place_relpaths()
INDEX_RELPATHS = load_index_relpaths()
