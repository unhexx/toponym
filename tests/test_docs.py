from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "design" / "2026-09-09-v1-local-registries.md"

# Living snapshot must not describe the P5-era tree as current.
STALE_SNAPSHOT_PHRASES = (
    "**Next cycle is P6-INDEX.**",
    "Remaining v1 work is P6 FTS",
    "**Empty on every curated row**",
    "**No** `index.py` yet.",
    "`docs/SOURCES.md` | **Missing.**",
    "P6 PENDING",
    "P6-INDEX  (**next**)",
    "Live `geonames` cells are empty",
    "every `geonames` cell empty",
)


def test_design_snapshot_is_released_v1() -> None:
    text = DESIGN.read_text(encoding="utf-8")
    for phrase in STALE_SNAPSHOT_PHRASES:
        assert phrase not in text, phrase
    assert "v1 is released" in text
    assert "2026.09.09" in text
    assert "wd:Q649" in text and "524901" in text
    assert "wd:Q626" in text and "472776" in text
    assert "`index.py` present" in text or "scripts/index.py" in text
