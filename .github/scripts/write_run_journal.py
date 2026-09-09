#!/usr/bin/env python3
"""Write data/sources/runs/YYYY-MM-DD.json for the daily workflow soft path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--check-exit", required=True)
    parser.add_argument("--changed-count", type=int, required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    check_exit: int | str
    if args.check_exit.isdigit():
        check_exit = int(args.check_exit)
    else:
        check_exit = args.check_exit

    path = Path("data/sources/runs") / f"{args.today}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "as_of": args.as_of,
        "changed_count": args.changed_count,
        "error_count": 0,
        "sources": [],
        "records_upserted": 0,
        "records_deprecated": 0,
        "commit": None,
        "check_exit": check_exit,
    }
    if args.notes:
        payload["notes"] = args.notes
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
