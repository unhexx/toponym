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


class _CatalogDumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, data: str) -> Any:
    style = None
    lowered = data.lower()
    if data == "" or lowered in {"true", "false", "yes", "no", "on", "off", "null"}:
        style = '"'
    elif data.isdigit() or (data[:1] in "+-" and data[1:].isdigit()):
        style = '"'
    elif len(data) == 10 and data[4] == "-" and data[7] == "-":
        style = '"'
    elif '"' in data and "'" not in data:
        style = "'"
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_CatalogDumper.add_representer(str, _represent_str)


def dump_catalog(path: Path | str, payload: dict[str, Any]) -> None:
    path = Path(path)
    text = yaml.dump(
        payload,
        Dumper=_CatalogDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


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


def load_mapping(root: Path, source_id: str) -> dict[str, Any] | None:
    mappings_dir = Path(root) / "data" / "mappings"
    if not mappings_dir.is_dir():
        return None
    for path in sorted(mappings_dir.glob("*.yaml")):
        payload = stringify_dates(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        if isinstance(payload, dict) and payload.get("source_id") == source_id:
            return payload
    return None


def patch_catalog_source(
    path: Path | str,
    source_id: str,
    *,
    checked_at: str | None = None,
    cursor: str | None = None,
) -> bool:
    path = Path(path)
    catalog = load_catalog(path)
    source = get_source(catalog, source_id)
    changed = False
    if checked_at is not None and source.get("checked_at") != checked_at:
        source["checked_at"] = checked_at
        changed = True
    if cursor is not None and source.get("cursor") != cursor:
        source["cursor"] = cursor
        changed = True
    if not changed:
        return False
    dump_catalog(path, catalog)
    return True


def stamp_catalog_updated(path: Path | str, today: str) -> bool:
    """Set catalog.updated to today if it differs."""
    path = Path(path)
    catalog = load_catalog(path)
    if catalog.get("updated") == today:
        return False
    catalog["updated"] = today
    dump_catalog(path, catalog)
    return True


def stamp_catalog_checked_at(path: Path | str, today: str) -> bool:
    """Set catalog.updated and each source.checked_at to today if they differ."""
    path = Path(path)
    catalog = load_catalog(path)
    changed = False
    if catalog.get("updated") != today:
        catalog["updated"] = today
        changed = True
    for source in catalog.get("sources", []):
        if source.get("checked_at") != today:
            source["checked_at"] = today
            changed = True
    if changed:
        dump_catalog(path, catalog)
    return changed
