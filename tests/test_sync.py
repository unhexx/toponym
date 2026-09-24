from __future__ import annotations

import csv
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

import scripts.lib.harvest as harvest_mod
import scripts.sync as sync_mod
from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.harvest import SPARQL_ENDPOINT
from scripts.lib.places import AGENCIES_SCHEMA, PLACES_SCHEMA
from scripts.lib.upsert import UpsertCounts

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXED_NOW = datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = headers or {}
        self.ok = 200 <= status_code < 400
        self.raw = None

    def close(self) -> None:
        return None


class FakeSession:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[dict] = []

    def request(self, method: str, url: str, **kwargs):
        method = method.upper()
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        result = self.handler(method, url, kwargs)
        if isinstance(result, BaseException):
            raise result
        return result

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def head(self, url: str, **kwargs):
        return self.request("HEAD", url, **kwargs)


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _sparql_csv(rows: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["item", "ru", "en", "lat", "lon", "gn", "oktmo"]
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    return buf.getvalue()


def _wikidata_handler(
    rows_by_qid: dict[str, dict[str, str]],
    extra: dict[str, dict[str, str]] | None = None,
):
    extra = extra or {}

    def handler(method: str, url: str, kwargs: dict):
        if SPARQL_ENDPOINT not in url and "query.wikidata.org" not in url:
            return FakeResponse(status_code=404)
        query = (kwargs.get("params") or {}).get("query") or ""
        asked = re.findall(r"wd:(Q\d+)", query)
        out: list[dict[str, str]] = []
        for qid in asked:
            row = rows_by_qid.get(qid)
            if row is not None:
                payload = dict(row)
                payload.setdefault("item", f"http://www.wikidata.org/entity/{qid}")
                out.append(payload)
        for qid, row in extra.items():
            payload = dict(row)
            payload.setdefault("item", f"http://www.wikidata.org/entity/{qid}")
            out.append(payload)
        return FakeResponse(text=_sparql_csv(out))

    return handler


def _prepare_wikidata_root(tmp_path: Path) -> Path:
    (tmp_path / "data" / "sources").mkdir(parents=True)
    (tmp_path / "data" / "curated").mkdir(parents=True)
    (tmp_path / "data" / "mappings").mkdir(parents=True)
    payload = {
        "resources": [
            {
                "name": "cities-major",
                "path": "data/curated/cities-major.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "municipalities",
                "path": "data/curated/municipalities.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "hodonyms",
                "path": "data/curated/hodonyms.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "microtoponyms",
                "path": "data/curated/microtoponyms.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "villages",
                "path": "data/curated/villages.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "hydronyms-major",
                "path": "data/curated/hydronyms-major.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "oronyms-major",
                "path": "data/curated/oronyms-major.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "agoronyms",
                "path": "data/curated/agoronyms.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "dromonyms",
                "path": "data/curated/dromonyms.csv",
                "schema": PLACES_SCHEMA,
            },
            {
                "name": "agencies-foiv",
                "path": "data/curated/agencies-foiv.csv",
                "schema": AGENCIES_SCHEMA,
            },
        ]
    }
    (tmp_path / "datapackage.json").write_text(json.dumps(payload), encoding="utf-8")
    shutil_catalog = FIXTURES / "catalog_sync_wikidata.yaml"
    (tmp_path / "data/sources/catalog.yaml").write_text(
        shutil_catalog.read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_csv(
        tmp_path / "data/curated/cities-major.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q649",
                id_scheme="wikidata",
                type_id="city",
                name_ru="Москва",
                wd="",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/municipalities.csv",
        PLACES_HEADER,
        [
            _place(
                id="local:mun:kazan-go",
                id_scheme="local",
                type_id="municipality",
                name_ru="Казань",
                wd="Q12167762",
                oktmo="92701000",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/hodonyms.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q1644209",
                id_scheme="wikidata",
                type_id="hodonym",
                name_ru="Тверская улица",
                lat="55.7",
                lon="37.6",
                wd="Q1644209",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/microtoponyms.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q22698",
                id_scheme="wikidata",
                type_id="microtoponym",
                name_ru="Нескучный сад",
                wd="Q22698",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/villages.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q894049",
                id_scheme="wikidata",
                type_id="village",
                name_ru="Бородино",
                wd="Q894049",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/hydronyms-major.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q626",
                id_scheme="wikidata",
                type_id="potamonym",
                name_ru="Волга",
                wd="Q626",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/oronyms-major.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q43105",
                id_scheme="wikidata",
                type_id="oronym",
                name_ru="Эльбрус",
                wd="Q43105",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/agoronyms.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q41116",
                id_scheme="wikidata",
                type_id="agoronym",
                name_ru="Красная площадь",
                wd="Q41116",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/dromonyms.csv",
        PLACES_HEADER,
        [
            _place(
                id="wd:Q58767",
                id_scheme="wikidata",
                type_id="dromonym",
                name_ru="Транссибирская магистраль",
                wd="Q58767",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    write_csv(
        tmp_path / "data/curated/agencies-foiv.csv",
        PLACES_HEADER,
        [
            _place(
                id="foiv:mvd",
                id_scheme="foiv",
                type_id="agency",
                name_ru="МВД",
                wd="Q2114322",
                source_id="wikidata",
                status="active",
            )
        ],
    )
    return tmp_path


def _bindings() -> dict[str, dict[str, str]]:
    return {
        "Q649": {
            "ru": "Москва",
            "en": "Moscow",
            "lat": "55.75222",
            "lon": "37.61556",
            "gn": "524901",
            "oktmo": "45000000",
        },
        "Q12167762": {
            "ru": "городской округ Казань",
            "en": "Kazan Urban Okrug",
            "lat": "55.79028",
            "lon": "49.11444",
            "oktmo": "92701000",
        },
        "Q1644209": {
            "ru": "Тверская улица",
            "en": "Tverskaya Street",
            "lat": "55.7576",
            "lon": "37.6137",
            "gn": "6956712",
        },
        "Q22698": {
            "ru": "Нескучный сад",
            "en": "Neskuchny Garden",
            "gn": "123",
        },
        "Q894049": {
            "ru": "Бородино",
            "en": "Borodino",
            "lat": "55.526",
            "lon": "35.821",
            "gn": "572438",
        },
        "Q626": {
            "ru": "Волга",
            "en": "Volga",
            "lat": "45.7",
            "lon": "47.9",
            "gn": "472756",
        },
        "Q43105": {
            "ru": "Эльбрус",
            "en": "Elbrus",
            "lat": "43.355",
            "lon": "42.439",
            "gn": "563532",
        },
        "Q41116": {
            "ru": "Красная площадь",
            "en": "Red Square",
            "lat": "55.7539",
            "lon": "37.6208",
        },
        "Q58767": {
            "ru": "Транссибирская магистраль",
            "en": "Trans-Siberian Railway",
            "gn": "2013346",
        },
        "Q2114322": {
            "ru": "МВД России",
            "en": "Ministry of Internal Affairs",
        },
    }


def _patch_sync(monkeypatch, tmp_path: Path, session: FakeSession | None) -> None:
    monkeypatch.setattr(sync_mod, "ROOT", tmp_path)
    monkeypatch.setattr(sync_mod, "CATALOG_PATH", tmp_path / "data/sources/catalog.yaml")
    monkeypatch.setattr(sync_mod, "utcnow", lambda: FIXED_NOW)
    monkeypatch.setattr(harvest_mod.time, "sleep", lambda _s: None)
    if session is not None:
        monkeypatch.setattr(sync_mod, "build_session", lambda: session)


def test_sync_wikidata_fills_empty_across_all_seed_tables(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = _prepare_wikidata_root(tmp_path)
    extra = {
        "Q99999999": {
            "ru": "не из канона",
            "en": "unknown",
            "lat": "1",
            "lon": "2",
        }
    }
    session = FakeSession(_wikidata_handler(_bindings(), extra=extra))
    _patch_sync(monkeypatch, root, session)
    code = sync_mod.main(["--source", "wikidata", "--apply"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["inserted"] == 0
    assert report["updated"] >= 9
    assert report["skipped_unmapped"] == 1
    assert report["deprecated"] == 0

    _h, cities = read_csv(root / "data/curated/cities-major.csv")
    assert len(cities) == 1
    assert cities[0]["id"] == "wd:Q649"
    assert cities[0]["wd"] == "Q649"
    assert cities[0]["lat"] == "55.75222"
    assert cities[0]["geonames"] == "524901"
    assert cities[0]["name_en"] == "Moscow"
    assert cities[0]["name_ru"] == "Москва"
    assert cities[0]["oktmo"] == "45000000"

    _h, mun = read_csv(root / "data/curated/municipalities.csv")
    assert [row["id"] for row in mun] == ["local:mun:kazan-go"]
    assert mun[0]["lat"] == "55.79028"
    assert mun[0]["wd"] == "Q12167762"
    assert mun[0]["name_ru"] == "Казань"
    assert not any(row["id"].startswith("wd:") for row in mun)

    _h, hod = read_csv(root / "data/curated/hodonyms.csv")
    assert hod[0]["lat"] == "55.7"
    assert hod[0]["name_en"] == "Tverskaya Street"
    assert hod[0]["geonames"] == "6956712"

    _h, micro = read_csv(root / "data/curated/microtoponyms.csv")
    assert micro[0]["geonames"] == "123"
    assert micro[0]["name_en"] == "Neskuchny Garden"

    _h, villages = read_csv(root / "data/curated/villages.csv")
    assert villages[0]["id"] == "wd:Q894049"
    assert villages[0]["name_en"] == "Borodino"
    assert villages[0]["geonames"] == "572438"
    assert villages[0]["name_ru"] == "Бородино"

    _h, hydro = read_csv(root / "data/curated/hydronyms-major.csv")
    assert hydro[0]["id"] == "wd:Q626"
    assert hydro[0]["name_en"] == "Volga"
    assert hydro[0]["geonames"] == "472756"

    _h, oro = read_csv(root / "data/curated/oronyms-major.csv")
    assert oro[0]["id"] == "wd:Q43105"
    assert oro[0]["name_en"] == "Elbrus"
    assert oro[0]["geonames"] == "563532"

    _h, ago = read_csv(root / "data/curated/agoronyms.csv")
    assert ago[0]["id"] == "wd:Q41116"
    assert ago[0]["name_en"] == "Red Square"

    _h, dro = read_csv(root / "data/curated/dromonyms.csv")
    assert dro[0]["id"] == "wd:Q58767"
    assert dro[0]["name_en"] == "Trans-Siberian Railway"
    assert dro[0]["geonames"] == "2013346"

    _h, agencies = read_csv(root / "data/curated/agencies-foiv.csv")
    assert agencies[0]["id"] == "foiv:mvd"
    assert agencies[0]["name_en"] == "Ministry of Internal Affairs"
    assert agencies[0]["name_ru"] == "МВД"

    catalog = yaml.safe_load((root / "data/sources/catalog.yaml").read_text(encoding="utf-8"))
    wd = next(row for row in catalog["sources"] if row["id"] == "wikidata")
    assert str(wd["checked_at"]) == "2026-09-09"
    assert wd["detector"]["kind"] == "none"

    queries = [
        str(call["kwargs"].get("params", {}).get("query") or "") for call in session.calls
    ]
    joined = " ".join(queries)
    for qid in (
        "Q649",
        "Q12167762",
        "Q1644209",
        "Q22698",
        "Q894049",
        "Q626",
        "Q43105",
        "Q41116",
        "Q58767",
        "Q2114322",
    ):
        assert f"wd:{qid}" in joined
    assert "VALUES ?item" in joined
    canon = (*cities, *mun, *hod, *micro, *villages, *hydro, *oro, *ago, *dro, *agencies)
    assert not any(row["id"] == "wd:Q99999999" for row in canon)
    assert len(cities) == 1
    assert len(villages) == 1
    assert len(hydro) == 1
    assert len(oro) == 1


def test_sync_wikidata_dry_run_does_not_write(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = _prepare_wikidata_root(tmp_path)
    before = (root / "data/curated/cities-major.csv").read_bytes()
    catalog_before = (root / "data/sources/catalog.yaml").read_bytes()
    session = FakeSession(_wikidata_handler(_bindings()))
    _patch_sync(monkeypatch, root, session)
    code = sync_mod.main(["--source", "wikidata"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["apply"] is False
    assert report["updated"] >= 1
    assert (root / "data/curated/cities-major.csv").read_bytes() == before
    assert (root / "data/sources/catalog.yaml").read_bytes() == catalog_before


def test_sync_wikidata_refuses_insert(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = _prepare_wikidata_root(tmp_path)
    session = FakeSession(_wikidata_handler(_bindings()))
    _patch_sync(monkeypatch, root, session)

    def fake_upsert(existing, incoming, *, header, **kwargs):
        return existing, UpsertCounts(inserted=1)

    monkeypatch.setattr(sync_mod, "upsert_rows", fake_upsert)
    cities_before = (root / "data/curated/cities-major.csv").read_bytes()
    villages_before = (root / "data/curated/villages.csv").read_bytes()
    code = sync_mod.main(["--source", "wikidata", "--apply"])
    assert code == 2
    err = capsys.readouterr().err
    assert "не вставляет" in err
    assert (root / "data/curated/cities-major.csv").read_bytes() == cities_before
    assert (root / "data/curated/villages.csv").read_bytes() == villages_before


def test_sync_wikidata_sparql_error_exit_2(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = _prepare_wikidata_root(tmp_path)

    def handler(_method: str, url: str, _kwargs: dict):
        if "query.wikidata.org" in url:
            return FakeResponse(status_code=500, text="boom")
        return FakeResponse(status_code=404)

    _patch_sync(monkeypatch, root, FakeSession(handler))
    cities_before = (root / "data/curated/cities-major.csv").read_bytes()
    code = sync_mod.main(["--source", "wikidata", "--apply"])
    assert code == 2
    err = capsys.readouterr().err
    assert "SPARQL" in err or "500" in err
    assert (root / "data/curated/cities-major.csv").read_bytes() == cities_before
