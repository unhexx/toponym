#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from frictionless import Package  # noqa: E402

from scripts.lib.catalog import catalog_source_ids, load_catalog  # noqa: E402
from scripts.lib.csvio import read_csv  # noqa: E402
from scripts.lib.declensions import uniqueness_key  # noqa: E402
from scripts.lib.invariants import (  # noqa: E402
    check_frozen_taxonomy,
    check_gn_id,
    check_gold_auto,
    check_name_yo,
    check_sharealike,
    issue,
)

ROOT = _ROOT
DATAPACKAGE = ROOT / "datapackage.json"
CATALOG_PATH = ROOT / "data" / "sources" / "catalog.yaml"
MAX_BYTES = 10 * 1024 * 1024
STATUS_ENUM = {"active", "deprecated"}
TOROPUM_NAMES = frozenset({"торопум", "toropum"})
PLACE_SCHEMAS = {
    "schema/table/places.schema.json",
    "schema/table/agencies.schema.json",
}


class ValidateCrash(Exception):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Frictionless и инварианты канона toponym")
    parser.add_argument("--datapackage", metavar="PATH", default=str(DATAPACKAGE))
    parser.add_argument("--json", action="store_true", help="печатать JSON-отчёт")
    return parser.parse_args(argv)


def _load_package(dp_path: Path) -> dict[str, Any]:
    return json.loads(dp_path.read_text(encoding="utf-8"))


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def validate_tree(dp_path: Path, *, root: Path | None = None) -> tuple[int, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    if not dp_path.is_file():
        raise ValidateCrash(f"нет datapackage: {dp_path}")
    base = dp_path.parent
    root = root or base
    try:
        descriptor = _load_package(dp_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidateCrash(f"не удалось прочитать datapackage: {exc}") from exc

    try:
        package = Package(str(dp_path), basepath=str(base))
        report = package.validate()
        if not report.valid:
            for item in report.flatten(["type", "message"]):
                kind, message = (item + ["", ""])[:2]
                issue(errors, "frictionless", f"{kind}: {message}")
    except Exception as exc:
        issue(errors, "frictionless", str(exc))

    resources = descriptor.get("resources") or []
    tables: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    for resource in resources:
        name = resource.get("name") or resource.get("path") or "?"
        rel = resource.get("path")
        if not rel:
            issue(errors, "resource", "нет path", name)
            continue
        path = (base / rel).resolve()
        if not path.is_file():
            raise ValidateCrash(f"нет ресурса {name}: {path}")
        raw = _read_bytes(path)
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            issue(errors, "encoding", f"не UTF-8: {exc}", name)
            continue
        if b"\r" in raw:
            issue(errors, "crlf", "файл содержит CR", name)
        if resource.get("encoding") and resource["encoding"].lower() != "utf-8":
            issue(errors, "encoding", f"encoding={resource['encoding']}", name)
        dialect = resource.get("dialect") or {}
        if dialect.get("delimiter") not in (None, ","):
            issue(errors, "delimiter", f"delimiter={dialect.get('delimiter')}", name)
        header, rows = read_csv(path)
        if not header:
            issue(errors, "rows", "нет заголовка", name)
        if len(rows) < 1:
            issue(errors, "rows", "нет строк данных", name)
        tables[name] = (header, rows)

    catalog_ids: set[str] = set()
    catalog_file = root / "data" / "sources" / "catalog.yaml"
    if catalog_file.is_file():
        catalog_ids = catalog_source_ids(load_catalog(catalog_file))

    type_ids: set[str] = set()
    if "types" in tables:
        type_ids = {row["id"] for row in tables["types"][1] if row.get("id")}

    place_names = [
        resource.get("name")
        for resource in resources
        if resource.get("schema") in PLACE_SCHEMAS
    ]
    union_set: set[str] = set()
    for name in place_names:
        if name not in tables:
            continue
        _header, rows = tables[name]
        seen: set[str] = set()
        for row in rows:
            rid = row.get("id") or ""
            if not rid:
                issue(errors, "id", "пустой id", name)
                continue
            check_gn_id(rid, name, errors)
            if rid in seen:
                issue(errors, "unique", f"повтор id {rid}", name)
            seen.add(rid)
            if rid in union_set:
                issue(errors, "unique", f"повтор id {rid} между таблицами", name)
            union_set.add(rid)

    for name, (header, rows) in tables.items():
        if "id" in header and name not in place_names:
            seen: set[tuple[str, str]] = set()
            by_lemma = "lemma" in header
            for row in rows:
                rid = row.get("id") or ""
                if not rid:
                    issue(errors, "id", "пустой id", name)
                    continue
                key = uniqueness_key(row) if by_lemma else (rid, "")
                if key in seen:
                    label = f"{key[0]}/{key[1]}" if by_lemma and key[1] else rid
                    issue(errors, "unique", f"повтор id {label}", name)
                seen.add(key)

        for row in rows:
            if "type_id" in header and name != "types":
                tid = row.get("type_id") or ""
                if type_ids and tid not in type_ids:
                    issue(errors, "type_id", f"{row.get('id')}: type_id={tid}", name)
            if "source_id" in header and name != "types":
                sid = row.get("source_id") or ""
                if catalog_ids and sid not in catalog_ids:
                    issue(errors, "source_id", f"{row.get('id')}: source_id={sid}", name)
                check_sharealike(row, name, errors)
            if "status" in header:
                status = row.get("status") or ""
                if status not in STATUS_ENUM:
                    issue(errors, "status", f"{row.get('id')}: status={status}", name)
            for col in ("id", "name_ru", "name_en"):
                if col in header and (row.get(col) or "").casefold() in TOROPUM_NAMES:
                    issue(errors, "toropum", f"{col}={row.get(col)}", name)
            if "name_ru" in header:
                check_name_yo(row, name, errors)
            if "review" in header:
                check_gold_auto(row, name, errors)

    if "types" in tables:
        _, type_rows = tables["types"]
        check_frozen_taxonomy(type_rows, errors)
        for row in type_rows:
            parent = row.get("parent_id") or ""
            if parent and parent not in type_ids:
                issue(errors, "parent_id", f"{row.get('id')}: parent_id={parent}", "types")

    for name in place_names:
        if name not in tables:
            continue
        _, rows = tables[name]
        for row in rows:
            parent = row.get("parent_id") or ""
            if parent and parent not in union_set:
                issue(errors, "parent_id", f"{row.get('id')}: parent_id={parent}", name)

    data_dir = root / "data"
    if data_dir.is_dir():
        for path in data_dir.rglob("*"):
            if path.is_file() and path.stat().st_size > MAX_BYTES:
                issue(errors, "size", f"{path.relative_to(root)} > 10MB")

    if "regions" in tables:
        _, regions = tables["regions"]
        isos = [row.get("iso") or "" for row in regions]
        nonempty = [iso for iso in isos if iso]
        if len(nonempty) != len(set(nonempty)):
            issue(errors, "iso", "iso субъектов не уникален", "regions")
        if len(regions) != 89:
            issue(errors, "count", f"regions={len(regions)}, ожидалось 89", "regions")
    if "federal-districts" in tables:
        n_fo = len(tables["federal-districts"][1])
        if n_fo != 8:
            issue(errors, "count", f"federal-districts={n_fo}, ожидалось 8", "federal-districts")

    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dp_path = Path(args.datapackage)
    try:
        code, errors = validate_tree(dp_path, root=dp_path.parent)
    except ValidateCrash as exc:
        payload = {"ok": False, "errors": [{"check": "crash", "message": str(exc)}]}
        if args.json:
            json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        if args.json:
            json.dump(
                {"ok": False, "errors": [{"check": "crash", "message": str(exc)}]},
                sys.stdout,
                ensure_ascii=False,
                indent=2,
            )
            sys.stdout.write("\n")
        else:
            print(str(exc), file=sys.stderr)
        return 2

    payload = {"ok": code == 0, "error_count": len(errors), "errors": errors}
    if args.json:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        if errors:
            for row in errors:
                loc = f"{row.get('resource')} " if row.get("resource") else ""
                print(f"{row['check']}: {loc}{row['message']}")
        else:
            print("ok")
    return code


if __name__ == "__main__":
    sys.exit(main())
