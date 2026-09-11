#!/usr/bin/env python3
"""Append a declension row to data/declensions/queue.csv. Never writes gold tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.lib.declensions import (  # noqa: E402
    DECLENSIONS_HEADER,
    DeclensionError,
    append_queue,
)

ROOT = _ROOT


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Очередь автосклонений: пишет только data/declensions/queue.csv (DEC-DECL-001)"
    )
    parser.add_argument("--id", required=True, help="стабильный id (wd:Q… / local:…)")
    parser.add_argument("--lemma", required=True, help="лемма")
    parser.add_argument("--type-code", default="", help="тип (city, hodonym, …)")
    parser.add_argument("--yo", default="")
    parser.add_argument("--gender", default="", choices=["", "m", "f", "n", "pl"])
    parser.add_argument(
        "--paradigm",
        default="",
        choices=[
            "",
            "noun_m2",
            "noun_f1",
            "noun_f3",
            "noun_n_ovo",
            "adj_m",
            "mixed_phrase",
            "pl_tantum",
            "indecl",
            "agency-head",
        ],
    )
    parser.add_argument(
        "--declinable",
        default="",
        choices=["", "always", "never", "optional", "not_with_generic"],
    )
    parser.add_argument("--nom", default="")
    parser.add_argument("--gen", default="")
    parser.add_argument("--dat", default="")
    parser.add_argument("--acc", default="")
    parser.add_argument("--ins", default="")
    parser.add_argument("--pre", default="")
    parser.add_argument("--loc2", default="")
    parser.add_argument(
        "--review",
        default="needs_review",
        help="auto или needs_review; gold запрещён",
    )
    parser.add_argument("--source", default="auto")
    parser.add_argument("--dry-run", action="store_true", help="не писать файл")
    parser.add_argument(
        "--root",
        default=str(ROOT),
        help="корень репозитория (по умолчанию этот клон)",
    )
    return parser.parse_args(argv)


def row_from_args(args: argparse.Namespace) -> dict[str, str]:
    row = {key: "" for key in DECLENSIONS_HEADER}
    row.update(
        {
            "id": args.id,
            "type_code": args.type_code,
            "lemma": args.lemma,
            "yo": args.yo,
            "gender": args.gender,
            "paradigm": args.paradigm,
            "declinable": args.declinable,
            "nom": args.nom or args.lemma,
            "gen": args.gen,
            "dat": args.dat,
            "acc": args.acc,
            "ins": args.ins,
            "pre": args.pre,
            "loc2": args.loc2,
            "review": args.review,
            "source": args.source,
        }
    )
    return row


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    try:
        path, added = append_queue(
            root,
            [row_from_args(args)],
            apply=not args.dry_run,
        )
    except DeclensionError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2
    rel = path if path.is_absolute() and root in path.parents else path
    try:
        shown = path.relative_to(root)
    except ValueError:
        shown = rel
    flag = "dry-run" if args.dry_run else "ok"
    print(f"{flag} added={added} path={shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
