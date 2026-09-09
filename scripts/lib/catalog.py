from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml


def stringify_dates(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: stringify_dates(item) for key, item in value.items()}
    if isinstance(value, list):
        return [stringify_dates(item) for item in value]
    return value


def load_catalog(path: Path | str) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"каталог {path} должен быть mapping")
    return stringify_dates(payload)


def catalog_source_ids(catalog: dict[str, Any]) -> set[str]:
    return {source["id"] for source in catalog.get("sources", [])}


def get_source(catalog: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in catalog.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise KeyError(source_id)


def iter_sources(
    catalog: dict[str, Any], source_id: str | None = None
) -> list[dict[str, Any]]:
    sources = list(catalog.get("sources", []))
    if source_id is None:
        return sources
    return [get_source(catalog, source_id)]
