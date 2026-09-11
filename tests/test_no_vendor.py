from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024
DUMP_NAMES = {"ru.zip", "gar.zip", "fias.zip"}
DUMP_SUFFIXES = {".zip", ".7z", ".rar"}


def _tracked_paths() -> list[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [item.decode("utf-8") for item in raw.split(b"\0") if item]


def test_no_tracked_file_over_10mb() -> None:
    oversized = []
    for rel in _tracked_paths():
        path = ROOT / rel
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_BYTES:
            oversized.append((rel, size))
    assert not oversized, oversized


def test_no_data_file_over_10mb_on_disk() -> None:
    oversized = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "data").rglob("*")
        if path.is_file() and path.stat().st_size > MAX_BYTES
    ]
    assert not oversized, oversized


def test_no_dump_archives_tracked_or_in_data() -> None:
    bad_tracked = [
        rel
        for rel in _tracked_paths()
        if Path(rel).name.casefold() in DUMP_NAMES
        or (rel.startswith("data/") and Path(rel).suffix.casefold() in DUMP_SUFFIXES)
    ]
    assert not bad_tracked, bad_tracked
    bad_disk = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "data").rglob("*")
        if path.is_file()
        and (
            path.name.casefold() in DUMP_NAMES
            or path.suffix.casefold() in DUMP_SUFFIXES
        )
    ]
    assert not bad_disk, bad_disk
