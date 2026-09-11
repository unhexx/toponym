from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.lib.csvio import read_csv, write_csv

DECLENSIONS_HEADER = [
    "id",
    "type_code",
    "lemma",
    "yo",
    "gender",
    "paradigm",
    "declinable",
    "nom",
    "gen",
    "dat",
    "acc",
    "ins",
    "pre",
    "loc2",
    "review",
    "source",
]
QUEUE_RELPATH = Path("data/declensions/queue.csv")
GOLD_RELPATHS = (
    Path("data/declensions/regions.csv"),
    Path("data/declensions/cities-major.csv"),
    Path("data/declensions/agencies.csv"),
    Path("data/declensions/hydronyms-major.csv"),
    Path("data/declensions/oronyms-major.csv"),
    Path("data/declensions/municipalities.csv"),
    Path("data/declensions/hodonyms.csv"),
    Path("data/declensions/microtoponyms.csv"),
)
AUTO_SOURCE_MARKERS = ("pymorphy", "natasha", "pyphrasy")
QUEUE_REVIEW = frozenset({"auto", "needs_review"})


class DeclensionError(Exception):
    pass


def is_auto_source(source: str) -> bool:
    text = (source or "").casefold()
    return any(marker in text for marker in AUTO_SOURCE_MARKERS)


def uniqueness_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("id") or ""), str(row.get("lemma") or ""))


def prepare_queue_row(row: dict[str, Any]) -> dict[str, str]:
    out = {key: str(row.get(key) or "") for key in DECLENSIONS_HEADER}
    if not out["id"] or not out["lemma"]:
        raise DeclensionError("нужны id и lemma")
    review = (out.get("review") or "needs_review").strip()
    if review == "gold":
        raise DeclensionError("очередь не принимает review=gold (DEC-DECL-001)")
    if review not in QUEUE_REVIEW:
        raise DeclensionError(f"review={review}: в очередь только auto или needs_review")
    out["review"] = review
    if not out["source"]:
        out["source"] = "auto"
    return out


def append_queue(
    root: Path,
    incoming: list[dict[str, Any]],
    *,
    apply: bool,
) -> tuple[Path, int]:
    path = Path(root) / QUEUE_RELPATH
    if path.is_file():
        header, existing = read_csv(path)
        if header != DECLENSIONS_HEADER:
            raise DeclensionError(f"очередь: неожиданный заголовок {header}")
    else:
        existing = []
    prepared = [prepare_queue_row(row) for row in incoming]
    seen = {(row.get("id"), row.get("lemma")) for row in existing}
    added: list[dict[str, str]] = []
    for row in prepared:
        key = (row["id"], row["lemma"])
        if key in seen:
            continue
        seen.add(key)
        added.append(row)
    if apply:
        write_csv(path, DECLENSIONS_HEADER, [*existing, *added])
    return path, len(added)
