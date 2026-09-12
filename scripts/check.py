#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.catalog import load_catalog, stamp_catalog_checked_at  # noqa: E402
from scripts.lib.detectors import build_session, check_catalog, exit_code, utcnow  # noqa: E402

CATALOG_PATH = _ROOT / "data" / "sources" / "catalog.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Детекторы обновлений источников toponym")
    parser.add_argument("--json", action="store_true", help="печатать JSON-отчёт")
    parser.add_argument("--source", metavar="ID", help="проверить один источник")
    parser.add_argument("--offline", action="store_true", help="без сети; ошибка, если kind≠none")
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="сдвинуть catalog.yaml updated/checked_at, без детекторов",
    )
    parser.add_argument(
        "--today",
        metavar="YYYY-MM-DD",
        help="дата для --stamp; без --stamp игнорируется (UTC сегодня по умолчанию)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.stamp:
        if args.json or args.source or args.offline:
            print("--stamp не сочетается с --json / --source / --offline", file=sys.stderr)
            return 2
        today = args.today or utcnow().strftime("%Y-%m-%d")
        stamp_catalog_checked_at(CATALOG_PATH, today)
        return 0
    try:
        catalog = load_catalog(CATALOG_PATH)
    except (OSError, ValueError) as exc:
        report = {
            "as_of": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sources": [],
            "changed_count": 0,
            "error_count": 1,
            "error": str(exc),
        }
        if args.json:
            json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"ошибка чтения каталога: {exc}", file=sys.stderr)
        return 2

    session = None if args.offline else build_session()
    report = check_catalog(
        catalog,
        source_id=args.source,
        session=session,
        now=utcnow(),
        offline=args.offline,
    )
    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for row in report["sources"]:
            flag = "ERROR" if row["error"] else ("CHANGED" if row["changed"] else "ok")
            print(f"{row['id']}\t{flag}\t{row['reason']}")
        print(f"changed_count={report['changed_count']} error_count={report['error_count']}")
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
