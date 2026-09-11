from __future__ import annotations

import re
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


def load_mapping(root: Path, source_id: str) -> dict[str, Any] | None:
    mappings_dir = Path(root) / "data" / "mappings"
    if not mappings_dir.is_dir():
        return None
    for path in sorted(mappings_dir.glob("*.yaml")):
        payload = stringify_dates(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        if isinstance(payload, dict) and payload.get("source_id") == source_id:
            return payload
    return None


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _replace_or_insert_field(body: str, field: str, value: str) -> str:
    pattern = re.compile(rf"^([ \t]*){re.escape(field)}:.*$", re.M)
    match = pattern.search(body)
    if match:
        return pattern.sub(rf"\1{field}: {value}", body, count=1)
    checked = re.search(r"^([ \t]*)checked_at:.*$", body, re.M)
    line = f"{field}: {value}"
    if checked:
        indent = checked.group(1)
        insert_at = checked.end()
        return body[:insert_at] + f"\n{indent}{line}" + body[insert_at:]
    indent = "    "
    if not body.endswith("\n"):
        body += "\n"
    return body + f"{indent}{line}\n"


def patch_catalog_source(
    path: Path | str,
    source_id: str,
    *,
    checked_at: str | None = None,
    cursor: str | None = None,
) -> bool:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(^[ \t]*- id: {re.escape(source_id)}\n)(.*?)(?=^[ \t]*- id: |\nwatchlist_github:|\Z)",
        re.M | re.S,
    )
    match = pattern.search(text)
    if not match:
        raise KeyError(source_id)
    prefix, body = match.group(1), match.group(2)
    if checked_at is not None:
        body = _replace_or_insert_field(body, "checked_at", checked_at)
    if cursor is not None:
        body = _replace_or_insert_field(body, "cursor", _yaml_quote(cursor))
    new = text[: match.start()] + prefix + body + text[match.end() :]
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def stamp_catalog_checked_at(path: Path | str, today: str) -> bool:
    """Set catalog.updated and each source.checked_at to today if they differ."""
    path = Path(path)
    catalog = load_catalog(path)
    changed = False
    text = path.read_text(encoding="utf-8")
    if catalog.get("updated") != today:
        new = re.sub(r"^updated:\s*.*$", f"updated: {today}", text, count=1, flags=re.M)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed = True
    for source in catalog.get("sources", []):
        source_id = source.get("id")
        if not source_id:
            continue
        if source.get("checked_at") == today:
            continue
        if patch_catalog_source(path, source_id, checked_at=today):
            changed = True
    return changed
