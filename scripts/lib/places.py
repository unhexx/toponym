from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
PLACES_SCHEMA = "schema/table/places.schema.json"
AGENCIES_SCHEMA = "schema/table/agencies.schema.json"


def _load_resources(datapackage: Path) -> list[dict[str, Any]]:
    payload = json.loads(datapackage.read_text(encoding="utf-8"))
    resources = payload.get("resources") or []
    return [res for res in resources if isinstance(res, dict)]


def _resource_path(path: object) -> str:
    if isinstance(path, str):
        return path
    if isinstance(path, list):
        raise ValueError(f"resource path must be a string, got list: {path!r}")
    return ""


def _paths_for_schema(resources: list[dict[str, Any]], schema: str) -> list[str]:
    paths: list[str] = []
    for res in resources:
        # same string refs as validate.PLACE_SCHEMAS; inline schema objects are skipped
        if res.get("schema") != schema:
            continue
        rel = _resource_path(res.get("path"))
        if rel:
            paths.append(rel)
    return paths


def _relpaths(root: Path) -> tuple[list[str], list[str]]:
    resources = _load_resources(root / "datapackage.json")
    places = _paths_for_schema(resources, PLACES_SCHEMA)
    return places, places + _paths_for_schema(resources, AGENCIES_SCHEMA)


def load_place_relpaths(root: Path | None = None) -> list[str]:
    return _relpaths(root or _ROOT)[0]


def load_index_relpaths(root: Path | None = None) -> list[str]:
    return _relpaths(root or _ROOT)[1]


def __getattr__(name: str) -> list[str]:
    if name not in {"PLACE_RELPATHS", "INDEX_RELPATHS"}:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    places, index = _relpaths(_ROOT)
    module = sys.modules[__name__]
    module.PLACE_RELPATHS = places
    module.INDEX_RELPATHS = index
    return places if name == "PLACE_RELPATHS" else index


def __dir__() -> list[str]:
    return sorted([*globals(), "PLACE_RELPATHS", "INDEX_RELPATHS"])
