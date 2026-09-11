from __future__ import annotations

import json
from pathlib import Path

from scripts.lib.csvio import read_csv

ROOT = Path(__file__).resolve().parents[1]
DATAPACKAGE = ROOT / "datapackage.json"
HFLABS_RAW = (
    ROOT / "data" / "raw" / "hflabs-region",
    ROOT / "data" / "raw" / "hflabs-city",
)
HFLABS_COLUMNS = {"kladr_id", "iso_3166-2", "fias_id", "federal_district"}
SHAREALIKE_IDS = {"hflabs-region", "hflabs-city"}


def test_hflabs_raw_is_pointer_only() -> None:
    for path in HFLABS_RAW:
        assert (path / "SOURCE.md").is_file(), path.name
        text = (path / "SOURCE.md").read_text(encoding="utf-8")
        assert "CC-BY-SA" in text
        assert "curated" in text.casefold() or "не копировать" in text
        assert "DEC-HFLABS-001" in text
        extras = [p.name for p in path.iterdir() if p.name != "SOURCE.md"]
        assert extras == [], extras


def test_curated_has_no_hflabs_tables_or_columns() -> None:
    curated = ROOT / "data" / "curated"
    for path in curated.glob("*.csv"):
        assert "hflabs" not in path.name
        header, rows = read_csv(path)
        assert not (HFLABS_COLUMNS & set(header)), path.name
        if "source_id" in header:
            bad = [row["id"] for row in rows if row.get("source_id") in SHAREALIKE_IDS]
            assert not bad, (path.name, bad)


def test_datapackage_excludes_hflabs_csv() -> None:
    pkg = json.loads(DATAPACKAGE.read_text(encoding="utf-8"))
    for resource in pkg["resources"]:
        rel = resource["path"]
        assert "hflabs" not in rel
        assert not rel.startswith("data/raw/hflabs")


def test_hflabs_mapping_is_pointer() -> None:
    for name in ("hflabs-region.yaml", "hflabs-city.yaml"):
        text = (ROOT / "data" / "mappings" / name).read_text(encoding="utf-8")
        assert "delete_policy: pointer" in text, name
        assert "CC-BY-SA" in text, name
        assert "не копировать" in text, name
    city = (ROOT / "data" / "mappings" / "hflabs-city.yaml").read_text(encoding="utf-8")
    assert "name_ru" not in city.split("notes:", 1)[0]
    assert "fias_id" in city
