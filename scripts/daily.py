#!/usr/bin/env python3
"""Daily driver: check → sync-changed → validate/index → journal+counts → stamp-on-noop."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.index import rebuild_index  # noqa: E402
from scripts.lib.catalog import load_catalog, stamp_catalog_checked_at  # noqa: E402
from scripts.lib.detectors import build_session, check_catalog, exit_code, utcnow  # noqa: E402
from scripts.lib.journal import write_run_journal  # noqa: E402
from scripts.lib.upsert import UpsertCounts  # noqa: E402
from scripts.sync import SyncError, run_sync  # noqa: E402
from scripts.validate import ValidateCrash, validate_tree  # noqa: E402

ROOT = _ROOT
CATALOG_REL = Path("data") / "sources" / "catalog.yaml"


def changed_source_ids(report: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for row in report.get("sources") or []:
        if not isinstance(row, dict):
            continue
        source_id = row.get("id")
        if source_id and row.get("changed") and not row.get("error"):
            ids.append(str(source_id))
    return ids


def revert_data(root: Path) -> None:
    subprocess.run(["git", "checkout", "--", "data"], cwd=root, check=False)


def run_daily(
    *,
    root: Path | None = None,
    now: datetime | None = None,
    session: Any = None,
    offline: bool = False,
) -> tuple[dict[str, Any], int]:
    root = root or ROOT
    current = now or utcnow()
    today = current.date().isoformat()
    as_of = (
        current.strftime("%Y-%m-%dT%H:%M:%SZ")
        if current.tzinfo
        else f"{current.isoformat()}Z"
    )
    catalog_path = root / CATALOG_REL
    runs_dir = root / "data" / "sources" / "runs"

    if not offline and session is None:
        session = build_session()

    try:
        catalog = load_catalog(catalog_path)
    except (OSError, ValueError) as exc:
        check_report: dict[str, Any] = {
            "as_of": as_of,
            "sources": [],
            "changed_count": 0,
            "error_count": 1,
            "error": str(exc),
        }
        check_exit = 2
    else:
        check_report = check_catalog(
            catalog, session=session, now=current, offline=offline
        )
        check_exit = exit_code(check_report)

    synced: list[str] = []
    sync_reports: list[dict[str, Any]] = []
    validate_status = "skip"
    stamped = False
    journal_path: Path | None = None

    if check_exit == 10:
        for source_id in changed_source_ids(check_report):
            report, code = run_sync(
                source_id=source_id,
                apply=True,
                manual_file=None,
                session=session,
                now=current,
                root=root,
                catalog_path=catalog_path,
                check_report=check_report,
            )
            if code != 0:
                raise SyncError(f"sync {source_id} exit {code}")
            sync_reports.append(report)
            synced.append(source_id)
        try:
            val, _errors = validate_tree(root / "datapackage.json", root=root)
        except ValidateCrash:
            val = 2
        if val != 0:
            revert_data(root)
            summary = {
                "today": today,
                "check_exit": check_exit,
                "synced": synced,
                "validate": "fail",
                "stamped": False,
                "records_upserted": 0,
                "records_deprecated": 0,
                "journal": None,
            }
            return summary, 1
        validate_status = "0"
        # Index is derived (gitignored); failure must not drop a valid upsert.
        out = root / "knowledge" / "registry.db"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            rebuild_index(root, out)
        except (OSError, ValueError, sqlite3.Error):
            pass

    total = UpsertCounts()
    for report in sync_reports:
        total.add(
            UpsertCounts(
                inserted=int(report.get("inserted") or 0),
                updated=int(report.get("updated") or 0),
                deprecated=int(report.get("deprecated") or 0),
            )
        )
    fields = total.journal_fields()
    upserted = fields["records_upserted"]
    deprecated = fields["records_deprecated"]

    journal_path = write_run_journal(
        today=today,
        as_of=as_of,
        check_exit=check_exit,
        check_report=check_report,
        runs_dir=runs_dir,
        records_upserted=upserted,
        records_deprecated=deprecated,
    )

    if check_exit == 0:
        stamped = bool(stamp_catalog_checked_at(catalog_path, today))

    summary = {
        "today": today,
        "check_exit": check_exit,
        "synced": synced,
        "validate": validate_status,
        "stamped": stamped,
        "records_upserted": upserted,
        "records_deprecated": deprecated,
        "journal": str(journal_path),
    }
    return summary, 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ежедневный прогон toponym")
    parser.add_argument("--offline", action="store_true", help="без сети; kind≠none → ошибка")
    parser.add_argument(
        "--root",
        default="",
        help="корень репозитория (по умолчанию рядом со scripts/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root) if args.root else ROOT
    try:
        summary, code = run_daily(root=root, offline=bool(args.offline))
    except (SyncError, OSError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
