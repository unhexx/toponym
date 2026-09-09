from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024


def test_no_tracked_file_over_10mb() -> None:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    paths = [item.decode("utf-8") for item in raw.split(b"\0") if item]
    oversized = []
    for rel in paths:
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
