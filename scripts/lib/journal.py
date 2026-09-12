"""Write data/sources/runs/YYYY-MM-DD.json for the daily driver."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_run_journal(
    *,
    today: str,
    as_of: str,
    check_exit: int | str,
    changed_count: int = 0,
    notes: str = "",
    check_json: Path | None = None,
    check_report: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
    records_upserted: int = 0,
    records_deprecated: int = 0,
) -> Path:
    payload: dict = {
        "as_of": as_of,
        "changed_count": changed_count,
        "error_count": 0,
        "sources": [],
        "records_upserted": records_upserted,
        "records_deprecated": records_deprecated,
        "commit": None,
        "check_exit": check_exit,
    }
    report: Any = check_report
    if report is None and check_json is not None:
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
