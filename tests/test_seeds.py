from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATAPACKAGE = ROOT / "datapackage.json"
TYPES_CSV = ROOT / "data" / "curated" / "types.csv"
MAX_BYTES = 10 * 1024 * 1024
FIXTURE_LEMMAS = {
    "Москва",
    "Нижний Новгород",
    "Сочи",
    "Орёл",
    "Пушкин",
    "Жуковский",
    "Домодедово",
    "Дон",
    "Волга",
    "МВД",
    "Министерство внутренних дел",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_fields(schema_rel: str) -> list[str]:
    schema = _load_json(ROOT / schema_rel)
    return [field["name"] for field in schema["fields"]]


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    assert b"\r" not in raw, path
    assert not raw.startswith(b"\xef\xbb\xbf"), path
    text = raw.decode("utf-8")
    assert text, path
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    return header, rows


def test_datapackage_paths_exist_with_rows() -> None:
    pkg = _load_json(DATAPACKAGE)
    for resource in pkg["resources"]:
        path = ROOT / resource["path"]
        assert path.is_file(), resource["name"]
        assert path.stat().st_size < MAX_BYTES, resource["path"]
        header, rows = _read_csv(path)
        assert header == _schema_fields(resource["schema"]), resource["name"]
        assert len(rows) >= 1, resource["name"]


def test_seed_counts() -> None:
    _, fo = _read_csv(ROOT / "data/curated/federal-districts.csv")
    _, regions = _read_csv(ROOT / "data/curated/regions.csv")
    _, cities = _read_csv(ROOT / "data/curated/cities-major.csv")
    _, hydros = _read_csv(ROOT / "data/curated/hydronyms-major.csv")
    _, oros = _read_csv(ROOT / "data/curated/oronyms-major.csv")
    _, foiv = _read_csv(ROOT / "data/curated/agencies-foiv.csv")
    _, other = _read_csv(ROOT / "data/curated/agencies-other.csv")
    _, mun = _read_csv(ROOT / "data/curated/municipalities.csv")
    _, hod = _read_csv(ROOT / "data/curated/hodonyms.csv")
    _, micro = _read_csv(ROOT / "data/curated/microtoponyms.csv")
    assert len(fo) == 8
    assert len(regions) == 89
    iso = [row["iso"] for row in regions if row["iso"]]
    assert len(iso) == 83
    assert len(set(iso)) == 83
    assert sum(1 for row in regions if row["id_scheme"] == "local") == 6
    assert len(cities) >= 150
    assert len(hydros) >= 40
    assert len(oros) >= 25
    assert len(foiv) >= 69
    assert len(other) >= 10
    assert len(mun) >= 1
    assert len(hod) >= 1
    assert len(micro) >= 1


def test_declension_ids_may_repeat() -> None:
    _, rows = _read_csv(ROOT / "data/declensions/agencies.csv")
    mvd = [row for row in rows if row["id"] == "foiv:mvd"]
    assert len(mvd) == 2
    assert {row["lemma"] for row in mvd} == {"МВД", "Министерство внутренних дел"}
    ids = [row["id"] for row in rows]
    assert len(ids) > len(set(ids))
    keys = [(row["id"], row["lemma"]) for row in rows]
    assert len(keys) == len(set(keys))
    assert all(not row["id"].endswith("#head") for row in rows)


def test_unique_ids_per_curated_file() -> None:
    pkg = _load_json(DATAPACKAGE)
    for resource in pkg["resources"]:
        path = ROOT / resource["path"]
        _header, rows = _read_csv(path)
        ids = [row["id"] for row in rows]
        if path.parent.name == "declensions":
            keys = [(row["id"], row["lemma"]) for row in rows]
            assert len(keys) == len(set(keys)), resource["name"]
            continue
        assert len(ids) == len(set(ids)), resource["name"]


def test_volga_and_mvd_present() -> None:
    _, hydros = _read_csv(ROOT / "data/curated/hydronyms-major.csv")
    _, foiv = _read_csv(ROOT / "data/curated/agencies-foiv.csv")
    assert any(row["name_ru"] == "Волга" for row in hydros)
    assert any(row["id"] == "wd:Q626" for row in hydros)
    assert any(row["id"] == "foiv:mvd" and row["abbr"] == "МВД" for row in foiv)


def test_no_gn_place_ids() -> None:
    pkg = _load_json(DATAPACKAGE)
    for resource in pkg["resources"]:
        _header, rows = _read_csv(ROOT / resource["path"])
        for row in rows:
            rid = row.get("id") or ""
            assert not rid.startswith("gn:"), (resource["name"], rid)


def test_geonames_fixtures_moscow_and_volga() -> None:
    _, cities = _read_csv(ROOT / "data/curated/cities-major.csv")
    moscow = next(row for row in cities if row["id"] == "wd:Q649")
    assert moscow["geonames"] == "524901"
    _, hydros = _read_csv(ROOT / "data/curated/hydronyms-major.csv")
    volga = next(row for row in hydros if row["id"] == "wd:Q626")
    assert volga["geonames"] == "472776"
    assert volga["geonames"] != "2022226"


def test_required_city_fixtures() -> None:
    _, cities = _read_csv(ROOT / "data/curated/cities-major.csv")
    names = {row["name_ru"] for row in cities}
    for name in (
        "Москва",
        "Санкт-Петербург",
        "Новосибирск",
        "Екатеринбург",
        "Казань",
        "Нижний Новгород",
        "Челябинск",
        "Самара",
        "Омск",
        "Ростов-на-Дону",
        "Уфа",
        "Красноярск",
        "Воронеж",
        "Пермь",
        "Волгоград",
        "Краснодар",
        "Сочи",
        "Орел",
        "Пушкин",
        "Жуковский",
        "Домодедово",
    ):
        assert name in names, name
    by_name = {row["name_ru"]: row for row in cities}
    assert by_name["Москва"]["id"] == "wd:Q649"
    assert by_name["Орел"]["name_yo"] == "Орёл"
    iso_subjects = {
        row["iso"]
        for row in _read_csv(ROOT / "data/curated/regions.csv")[1]
        if row["iso"]
    }
    assert all(row["admin1"] in iso_subjects for row in cities)


def test_oikonym_example_is_moscow() -> None:
    _header, rows = _read_csv(TYPES_CSV)
    oikonym = next(row for row in rows if row["id"] == "oikonym")
    assert oikonym["example_ru"] == "Москва"
    assert oikonym["geonames_class"] == "P"


def test_taxonomy_root_frozen() -> None:
    _header, rows = _read_csv(TYPES_CSV)
    by_id = {row["id"]: row for row in rows}
    assert by_id["toponym"]["level"] == "root"
    assert (by_id["toponym"]["parent_id"] or "") == ""
    assert by_id["toponym"]["name_en"] == "toponym"
    assert by_id["toponym"]["name_ru"] == "топоним"
    for tid in ("oikonym", "hydronym"):
        assert by_id[tid]["level"] == "primary"
        assert by_id[tid]["parent_id"] == "toponym"
    assert "торопум" not in {row["id"] for row in rows}


def test_no_toropum_in_id_or_names() -> None:
    pkg = _load_json(DATAPACKAGE)
    forbidden = {"торопум", "toropum"}
    for resource in pkg["resources"]:
        _header, rows = _read_csv(ROOT / resource["path"])
        for row in rows:
            for key in ("id", "name_ru", "name_en", "lemma"):
                value = (row.get(key, "") or "").casefold()
                assert value not in forbidden, (resource["name"], key, row.get(key))


def test_declension_fixtures_are_gold() -> None:
    rows: list[dict[str, str]] = []
    for name in ("regions.csv", "cities-major.csv", "agencies.csv"):
        _header, part = _read_csv(ROOT / "data" / "declensions" / name)
        rows.extend(part)
    by_lemma: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_lemma.setdefault(row["lemma"], []).append(row)
    for lemma in FIXTURE_LEMMAS:
        matches = by_lemma.get(lemma, [])
        assert matches, lemma
        gold = [row for row in matches if row["review"] == "gold"]
        assert gold, lemma
    pushkin = next(row for row in by_lemma["Пушкин"] if row["review"] == "gold")
    assert pushkin["ins"] == "Пушкином"
    don = next(row for row in by_lemma["Дон"] if row["review"] == "gold")
    assert don["loc2"] == "Дону"
    volga = next(row for row in by_lemma["Волга"] if row["review"] == "gold")
    assert volga["id"] == "wd:Q626"
    assert volga["gen"] == "Волги"
    assert volga["gen"] != "Волгы"


def test_name_ru_has_no_yo() -> None:
    for rel in (
        "data/curated/federal-districts.csv",
        "data/curated/regions.csv",
        "data/curated/cities-major.csv",
        "data/curated/hydronyms-major.csv",
        "data/curated/oronyms-major.csv",
        "data/curated/agencies-foiv.csv",
        "data/curated/agencies-other.csv",
        "data/curated/municipalities.csv",
        "data/curated/hodonyms.csv",
        "data/curated/microtoponyms.csv",
    ):
        _header, rows = _read_csv(ROOT / rel)
        for row in rows:
            assert "ё" not in row["name_ru"] and "Ё" not in row["name_ru"], row["id"]


def test_fmba_notes_mention_ukase_522() -> None:
    _header, rows = _read_csv(ROOT / "data/curated/agencies-foiv.csv")
    fmba = next(row for row in rows if row["id"] == "foiv:fmba")
    assert "522" in fmba["notes"]


def test_baikal_is_hydronym_not_oronym() -> None:
    _, hydros = _read_csv(ROOT / "data/curated/hydronyms-major.csv")
    _, oros = _read_csv(ROOT / "data/curated/oronyms-major.csv")
    assert any(row["name_ru"] == "Байкал" for row in hydros)
    assert all(row["name_ru"] != "Байкал" for row in oros)
    assert any(row["name_ru"] == "Эльбрус" for row in oros)
    assert any(row["name_ru"] == "Сахалин" and row["type_id"] == "insulonym" for row in oros)


def test_k_seed_types_and_parents() -> None:
    type_ids = {row["id"] for row in _read_csv(TYPES_CSV)[1]}
    assert {"municipality", "hodonym", "microtoponym"} <= type_ids
    _, mun = _read_csv(ROOT / "data/curated/municipalities.csv")
    _, hod = _read_csv(ROOT / "data/curated/hodonyms.csv")
    _, micro = _read_csv(ROOT / "data/curated/microtoponyms.csv")
    assert any(
        row["name_ru"] == "городской округ Самара" and row["type_id"] == "municipality"
        for row in mun
    )
    assert any(
        row["name_ru"] == "Тверская улица" and row["type_id"] == "hodonym" for row in hod
    )
    assert any(
        row["name_ru"] == "урочище Синие камни" and row["type_id"] == "microtoponym"
        for row in micro
    )
    assert all(row["type_id"] == "municipality" for row in mun)
    assert all(row["type_id"] == "hodonym" for row in hod)
    assert all(row["type_id"] == "microtoponym" for row in micro)
    union_ids = set()
    for rel in (
        "data/curated/federal-districts.csv",
        "data/curated/regions.csv",
        "data/curated/cities-major.csv",
        "data/curated/hydronyms-major.csv",
        "data/curated/oronyms-major.csv",
        "data/curated/municipalities.csv",
        "data/curated/hodonyms.csv",
        "data/curated/microtoponyms.csv",
        "data/curated/agencies-foiv.csv",
        "data/curated/agencies-other.csv",
    ):
        union_ids.update(row["id"] for row in _read_csv(ROOT / rel)[1])
    for row in (*mun, *hod, *micro):
        parent = row["parent_id"]
        assert parent, row["id"]
        assert parent in union_ids, (row["id"], parent)
    assert all(not row["id"].startswith("gn:") for row in (*mun, *hod, *micro))
    raw_dir = ROOT / "data"
    for path in raw_dir.rglob("*"):
        if path.is_file():
            assert path.stat().st_size < MAX_BYTES, path


def test_cities_not_seeded_in_local_subjects() -> None:
    _, regions = _read_csv(ROOT / "data/curated/regions.csv")
    local_iso = {row["iso"] for row in regions if row["id_scheme"] == "local" and row["iso"]}
    assert local_iso == set()
    local_ids = {row["id"] for row in regions if row["id_scheme"] == "local"}
    _, cities = _read_csv(ROOT / "data/curated/cities-major.csv")
    assert all(row["parent_id"] not in local_ids for row in cities)
