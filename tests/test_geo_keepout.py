from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_FIELDS = frozenset(
    {
        "population",
        "population_year",
        "geom",
        "geometry",
        "geojson",
        "wkt",
        "wkb",
        "polygon",
        "multipolygon",
        "postgis",
    }
)
def _schema_names(rel: str) -> list[str]:
    payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    return [field["name"] for field in payload["fields"]]


def test_places_schema_has_points_not_polygons() -> None:
    names = _schema_names("schema/table/places.schema.json")
    assert "lat" in names and "lon" in names
    assert not (FORBIDDEN_FIELDS & set(names))


def test_agencies_schema_has_no_geometry() -> None:
    names = _schema_names("schema/table/agencies.schema.json")
    assert not (FORBIDDEN_FIELDS & set(names))


def test_datapackage_has_no_geojson_resources() -> None:
    pkg = json.loads((ROOT / "datapackage.json").read_text(encoding="utf-8"))
    for resource in pkg["resources"]:
        path = resource["path"].casefold()
        assert not path.endswith((".geojson", ".gpkg", ".shp", ".sql"))
        assert "postgis" not in path
        assert "polygon" not in path


def test_pyproject_has_no_geo_stack() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8").casefold()
    for name in ("postgis", "geoalchemy", "shapely", "geopandas", "fiona"):
        assert name not in text, name


def test_sources_doc_points_outside_canon() -> None:
    text = (ROOT / "docs" / "SOURCES.md").read_text(encoding="utf-8")
    assert "DEC-GEO-001" in text
    assert "PostGIS" in text
    assert "GeoJSON" in text
    assert "населен" in text.casefold()
