#!/usr/bin/env python3
"""Write data/sources/runs/YYYY-MM-DD.json for the daily workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def journal_counts_from_sync_report(report: dict) -> tuple[int, int]:
    """Map sync.py / UpsertCounts JSON onto journal records_* fields."""
    if "records_upserted" in report or "records_deprecated" in report:
        return (
            int(report.get("records_upserted") or 0),
            int(report.get("records_deprecated") or 0),
        )
    upserted = int(report.get("inserted") or 0) + int(report.get("updated") or 0)
    deprecated = int(report.get("deprecated") or 0)
    return upserted, deprecated


def journal_counts_from_sync_files(paths: list[Path]) -> tuple[int, int]:
    upserted = 0
    deprecated = 0
    for path in paths:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            continue
        add_u, add_d = journal_counts_from_sync_report(report)
        upserted += add_u
        deprecated += add_d
    return upserted, deprecated


def write_run_journal(
    *,
    today: str,
    as_of: str,
    check_exit: int | str,
    changed_count: int = 0,
    notes: str = "",
    check_json: Path | None = None,
    runs_dir: Path | None = None,
    records_upserted: int | None = None,
    records_deprecated: int | None = None,
    sync_json: list[Path] | None = None,
) -> Path:
    from_sync_u, from_sync_d = journal_counts_from_sync_files(list(sync_json or []))
    payload: dict = {
        "as_of": as_of,
        "changed_count": changed_count,
        "error_count": 0,
        "sources": [],
        "records_upserted": from_sync_u if records_upserted is None else records_upserted,
        "records_deprecated": from_sync_d if records_deprecated is None else records_deprecated,
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--check-exit", required=True)
    parser.add_argument("--changed-count", type=int, default=0)
    parser.add_argument("--notes", default="")
    parser.add_argument("--check-json", default="")
    parser.add_argument("--records-upserted", type=int, default=None)
    parser.add_argument("--records-deprecated", type=int, default=None)
    parser.add_argument("--sync-json", action="append", default=[])
    args = parser.parse_args(argv)

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
        records_upserted=args.records_upserted,
        records_deprecated=args.records_deprecated,
        sync_json=[Path(p) for p in args.sync_json],
    )


if __name__ == "__main__":
    main()
