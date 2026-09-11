from __future__ import annotations

from typing import Any

from scripts.lib.declensions import is_auto_source

FROZEN_TAXONOMY = {
    "toponym": {"level": "root", "parent_id": ""},
    "oikonym": {"level": "primary", "parent_id": "toponym"},
    "hydronym": {"level": "primary", "parent_id": "toponym"},
}
SHAREALIKE_SOURCE_IDS = frozenset({"hflabs-region", "hflabs-city"})


def issue(
    errors: list[dict[str, Any]],
    check: str,
    message: str,
    resource: str | None = None,
) -> None:
    row: dict[str, Any] = {"check": check, "message": message}
    if resource:
        row["resource"] = resource
    errors.append(row)


def check_gn_id(
    rid: str,
    resource: str,
    errors: list[dict[str, Any]],
) -> None:
    if rid.startswith("gn:"):
        issue(errors, "gn_id", f"{rid}: gn: id запрещён (DEC-GN-001)", resource)


def check_sharealike(
    row: dict[str, str],
    resource: str,
    errors: list[dict[str, Any]],
) -> None:
    sid = row.get("source_id") or ""
    if sid in SHAREALIKE_SOURCE_IDS:
        issue(
            errors,
            "sharealike",
            f"{row.get('id')}: source_id={sid} (DEC-HFLABS-001)",
            resource,
        )


def check_gold_auto(
    row: dict[str, str],
    resource: str,
    errors: list[dict[str, Any]],
) -> None:
    if (row.get("review") or "") != "gold":
        return
    if is_auto_source(row.get("source") or ""):
        issue(
            errors,
            "gold_auto",
            f"{row.get('id')}: pymorphy/Natasha не золото (DEC-DECL-001)",
            resource,
        )


def yo_to_e(value: str) -> str:
    return value.replace("ё", "е").replace("Ё", "Е")


def check_name_yo(
    row: dict[str, str],
    resource: str,
    errors: list[dict[str, Any]],
) -> None:
    name_ru = row.get("name_ru") or ""
    name_yo = row.get("name_yo") or ""
    rid = row.get("id") or ""
    if "ё" in name_ru or "Ё" in name_ru:
        issue(errors, "yo", f"{rid}: ё в name_ru", resource)
    if not name_yo:
        return
    if "ё" not in name_yo and "Ё" not in name_yo:
        issue(errors, "yo", f"{rid}: name_yo без ё", resource)
        return
    if yo_to_e(name_yo) != name_ru:
        issue(errors, "yo", f"{rid}: name_ru не нормализация name_yo", resource)


def check_frozen_taxonomy(
    type_rows: list[dict[str, str]],
    errors: list[dict[str, Any]],
) -> None:
    by_type = {row.get("id"): row for row in type_rows if row.get("id")}
    for tid, expect in FROZEN_TAXONOMY.items():
        row = by_type.get(tid)
        if row is None:
            issue(errors, "taxonomy", f"нет типа {tid} (DEC-TAX-001)", "types")
            continue
        if (row.get("level") or "") != expect["level"]:
            issue(
                errors,
                "taxonomy",
                f"{tid}: level={row.get('level')} (DEC-TAX-001)",
                "types",
            )
        if (row.get("parent_id") or "") != expect["parent_id"]:
            issue(
                errors,
                "taxonomy",
                f"{tid}: parent_id={row.get('parent_id')} (DEC-TAX-001)",
                "types",
            )
