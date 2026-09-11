#!/usr/bin/env python3
"""Write data/sources/runs/YYYY-MM-DD.json for the daily workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.catalog import stamp_catalog_checked_at  # noqa: E402


def write_run_journal(
    *,
    today: str,
    as_of: str,
    check_exit: int | str,
    changed_count: int,
    notes: str = "",
    check_json: Path | None = None,
    runs_dir: Path | None = None,
) -> Path:
    payload: dict = {
        "as_of": as_of,
        "changed_count": changed_count,
        "error_count": 0,
        "sources": [],
        "records_upserted": 0,
        "records_deprecated": 0,
        "commit": None,
        "check_exit": check_exit,
    }
    if check_json is not None:
        report = json.loads(Path(check_json).read_text(encoding="utf-8"))
        if isinstance(report, dict):
            if report.get("as_of"):
                payload["as_of"] = report["as_of"]
            if "sources" in report and isinstance(report["sources"], list):
                payload["sources"] = report["sources"]
            if "changed_count" in report:
                payload["changed_count"] = int(report["changed_count"] or 0)
            if "error_count" in report:
                payload["error_count"] = int(report["error_count"] or 0)
    if notes:
        payload["notes"] = notes
    path = (runs_dir or Path("data/sources/runs")) / f"{today}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--check-exit", required=True)
    parser.add_argument("--changed-count", type=int, required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--check-json", default="")
    parser.add_argument(
        "--stamp-catalog",
        action="store_true",
        help="сдвинуть catalog.yaml updated/checked_at на --today, если устарели",
    )
    parser.add_argument("--catalog", default="data/sources/catalog.yaml")
    args = parser.parse_args()

    check_exit: int | str
    if args.check_exit.lstrip("-").isdigit():
        check_exit = int(args.check_exit)
    else:
        check_exit = args.check_exit

    check_json = Path(args.check_json) if args.check_json else None
    write_run_journal(
        today=args.today,
        as_of=args.as_of,
        check_exit=check_exit,
        changed_count=args.changed_count,
        notes=args.notes,
        check_json=check_json,
    )
    if args.stamp_catalog:
        stamp_catalog_checked_at(Path(args.catalog), args.today)


if __name__ == "__main__":
    main()
