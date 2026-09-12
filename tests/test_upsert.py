from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml

import scripts.sync as sync_mod
from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.upsert import apply_geonames, too_large, upsert_rows

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
        if "RU.zip" in url and method == "GET" and not kwargs.get("stream"):
            raise AssertionError("dump RU.zip must not be downloaded")
        result = self.handler(method, url, kwargs)
        if isinstance(result, BaseException):
            raise result
        return result

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def head(self, url: str, **kwargs):
        return self.request("HEAD", url, **kwargs)


def _geonames_handler(mods_body: str, deletes_body: str = ""):
    def handler(method: str, url: str, kwargs: dict):
        if "modifications-" in url:
            return FakeResponse(text=mods_body)
        if "deletes-" in url:
            return FakeResponse(text=deletes_body)
        if "RU.zip" in url:
            if method == "GET" and not kwargs.get("stream"):
                raise AssertionError("GET RU.zip")
            return FakeResponse(headers={"Content-Length": "99999999", "Last-Modified": "x"})
        return FakeResponse(status_code=404)

    return handler


def test_upsert_two_plus_new_is_three() -> None:
    header, existing = read_csv(FIXTURES / "places_two.csv")
    _, incoming = read_csv(FIXTURES / "places_incoming_new.csv")
    rows, counts = upsert_rows(existing, incoming, header=header)
    ids = [row["id"] for row in rows]
    assert len(rows) == 3
    assert ids[:2] == ["iso:RU-MOS", "iso:RU-SPE"]
    assert "iso:RU-TA" in ids
    assert counts.inserted == 1
    assert counts.updated == 0


def test_incoming_delete_deprecates_without_drop() -> None:
    header, existing = read_csv(FIXTURES / "places_two.csv")
    _, incoming = read_csv(FIXTURES / "places_incoming_delete.csv")
    rows, counts = upsert_rows(existing, incoming, header=header)
    assert len(rows) == 2
    by_id = {row["id"]: row for row in rows}
    assert by_id["iso:RU-MOS"]["status"] == "deprecated"
    assert by_id["iso:RU-MOS"]["replaced_by"] == "iso:RU-ME"
    assert by_id["iso:RU-SPE"]["status"] == "active"
    assert counts.deprecated == 1


def test_incoming_delete_without_replaced_by_leaves_empty() -> None:
    header, existing = read_csv(FIXTURES / "places_two.csv")
    incoming = [
        {
            "id": "iso:RU-SPE",
            "status": "deprecated",
            "replaced_by": "",
        }
    ]
    rows, _counts = upsert_rows(existing, incoming, header=header)
    by_id = {row["id"]: row for row in rows}
    assert by_id["iso:RU-SPE"]["status"] == "deprecated"
    assert by_id["iso:RU-SPE"]["replaced_by"] == ""


def test_geonames_match_without_insert() -> None:
    header, existing = read_csv(FIXTURES / "places_wd_moscow.csv")
    mods = (FIXTURES / "geonames_mods_moscow.tsv").read_text(encoding="utf-8")
    rows, counts = apply_geonames(existing, mods, today="2026-09-09")
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "wd:Q649"
    assert row["geonames"] == "524901"
    assert not any(item["id"].startswith("gn:") for item in rows)
    assert row["lat"] == "55.75222"
    assert row["lon"] == "37.61556"
    assert row["source_id"] == "wikidata"
    assert row["notes"] == "coords from geonames-ru"
    assert counts.updated == 1
    assert counts.inserted == 0
    _ = header


def test_geonames_unknown_id_not_inserted() -> None:
    _, existing = read_csv(FIXTURES / "places_wd_moscow.csv")
    mods = (FIXTURES / "geonames_mods_unknown.tsv").read_text(encoding="utf-8")
    rows, counts = apply_geonames(existing, mods, today="2026-09-09")
    assert len(rows) == 1
    assert rows[0]["id"] == "wd:Q649"
    assert rows[0]["lat"] == ""
    assert counts.skipped_unmapped == 1
    assert counts.inserted == 0
    assert not any(item["id"].startswith("gn:") for item in rows)
    before = [dict(row) for row in existing]
    again, counts2 = apply_geonames(before, mods + mods, today="2026-09-09")
    assert len(again) == len(existing)
    assert counts2.inserted == 0
    assert counts2.skipped_unmapped == 2


def test_gold_declension_not_overwritten() -> None:
    header, existing = read_csv(FIXTURES / "declensions_gold.csv")
    _, incoming = read_csv(FIXTURES / "declensions_incoming_overwrite.csv")
    rows, counts = upsert_rows(
        existing, incoming, header=header, gold_field="review", gold_value="gold"
    )
    assert len(rows) == 1
    assert rows[0]["lemma"] == "Москва"
    assert rows[0]["review"] == "gold"
    assert counts.skipped_gold == 1
    assert counts.updated == 0


def _prepare_root(tmp_path: Path) -> Path:
    (tmp_path / "data" / "sources").mkdir(parents=True)
    (tmp_path / "data" / "curated").mkdir(parents=True)
    (tmp_path / "data" / "mappings").mkdir(parents=True)
    shutil.copy(FIXTURES / "catalog_sync_geonames.yaml", tmp_path / "data/sources/catalog.yaml")
    shutil.copy(FIXTURES / "places_wd_moscow.csv", tmp_path / "data/curated/cities-major.csv")
    shutil.copy(ROOT / "data/mappings/geonames.yaml", tmp_path / "data/mappings/geonames.yaml")
    shutil.copy(ROOT / "data/mappings/ukase-326.yaml", tmp_path / "data/mappings/ukase-326.yaml")
    shutil.copy(
        ROOT / "data/mappings/fias-pointer.yaml", tmp_path / "data/mappings/fias-pointer.yaml"
    )
    empty_agencies = tmp_path / "data/curated/agencies-foiv.csv"
    write_csv(empty_agencies, PLACES_HEADER, [])
    return tmp_path


def _patch_sync(monkeypatch, tmp_path: Path, session: FakeSession | None) -> None:
    monkeypatch.setattr(sync_mod, "ROOT", tmp_path)
    monkeypatch.setattr(sync_mod, "CATALOG_PATH", tmp_path / "data/sources/catalog.yaml")
    monkeypatch.setattr(sync_mod, "utcnow", lambda: FIXED_NOW)
    if session is not None:
        monkeypatch.setattr(sync_mod, "build_session", lambda: session)


def test_default_dry_run_does_not_write(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _prepare_root(tmp_path)
    mods = (FIXTURES / "geonames_mods_moscow.tsv").read_text(encoding="utf-8")
    session = FakeSession(_geonames_handler(mods))
    _patch_sync(monkeypatch, root, session)
    before = (root / "data/curated/cities-major.csv").read_bytes()
    catalog_before = (root / "data/sources/catalog.yaml").read_bytes()
    code = sync_mod.main(["--source", "geonames-ru"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["apply"] is False
    assert report["updated"] == 1
    assert (root / "data/curated/cities-major.csv").read_bytes() == before
    assert (root / "data/sources/catalog.yaml").read_bytes() == catalog_before


def test_cli_geonames_apply_match_without_insert(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _prepare_root(tmp_path)
    mods = (FIXTURES / "geonames_mods_moscow.tsv").read_text(encoding="utf-8")
    unknown = (FIXTURES / "geonames_mods_unknown.tsv").read_text(encoding="utf-8")
    session = FakeSession(_geonames_handler(mods + unknown))
    _patch_sync(monkeypatch, root, session)
    code = sync_mod.main(["--source", "geonames-ru", "--apply"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    header, rows = read_csv(root / "data/curated/cities-major.csv")
    assert len(rows) == 1
    assert rows[0]["id"] == "wd:Q649"
    assert rows[0]["lat"] == "55.75222"
    assert not any(row["id"].startswith("gn:") for row in rows)
    assert report["updated"] == 1
    assert report["skipped_unmapped"] == 1
    assert report["inserted"] == 0
    catalog = yaml.safe_load((root / "data/sources/catalog.yaml").read_text(encoding="utf-8"))
    geo = next(s for s in catalog["sources"] if s["id"] == "geonames-ru")
    assert str(geo["checked_at"]) == "2026-09-09"
    assert any("modifications-2026-09-08.txt" in c["url"] for c in session.calls)
    assert not any(c["method"] == "GET" and "RU.zip" in c["url"] for c in session.calls)
    _ = header


def test_ukase_apply_without_manual_only_checked_at(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _prepare_root(tmp_path)
    _patch_sync(monkeypatch, root, FakeSession(_geonames_handler("")))
    agencies_before = (root / "data/curated/agencies-foiv.csv").read_bytes()
    code = sync_mod.main(["--source", "ukase-326", "--apply"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["inserted"] == 0
    assert (root / "data/curated/agencies-foiv.csv").read_bytes() == agencies_before
    catalog = yaml.safe_load((root / "data/sources/catalog.yaml").read_text(encoding="utf-8"))
    row = next(s for s in catalog["sources"] if s["id"] == "ukase-326")
    assert str(row["checked_at"]) == "2026-09-09"


def test_manual_file_requires_canonical_header(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _prepare_root(tmp_path)
    _patch_sync(monkeypatch, root, FakeSession(_geonames_handler("")))
    bad = tmp_path / "bad.csv"
    bad.write_text("id,name\nfoiv:x,X\n", encoding="utf-8")
    code = sync_mod.main(["--source", "ukase-326", "--apply", "--manual-file", str(bad)])
    assert code == 2
    err = capsys.readouterr().err
    assert "заголовок" in err.lower() or "header" in err.lower() or "канонический" in err


def test_check_json_cursor_applied_to_pointer_and_ukase(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = _prepare_root(tmp_path)
    catalog_path = root / "data/sources/catalog.yaml"
    text = catalog_path.read_text(encoding="utf-8")
    catalog_path.write_text(
        text.replace("updated: 2026-09-09", "updated: 2026-09-01"),
        encoding="utf-8",
    )
    check_json = tmp_path / "check.json"
    check_json.write_text(
        json.dumps(
            {
                "changed_count": 2,
                "error_count": 0,
                "sources": [
                    {
                        "id": "ukase-326",
                        "changed": True,
                        "error": False,
                        "cursor_new": "new-fingerprint",
                    },
                    {
                        "id": "fias-gar",
                        "changed": True,
                        "error": False,
                        "cursor_new": 'W/"etag"',
                    },
                    {
                        "id": "geonames-ru",
                        "changed": True,
                        "error": False,
                        "cursor_new": "2099-01-01",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _patch_sync(monkeypatch, root, FakeSession(_geonames_handler("")))
    code = sync_mod.main(["--apply", "--check-json", str(check_json)])
    assert code == 0
    json.loads(capsys.readouterr().out)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    assert str(catalog["updated"]) == "2026-09-09"
    by_id = {row["id"]: row for row in catalog["sources"]}
    assert str(by_id["ukase-326"]["cursor"]) == "new-fingerprint"
    assert str(by_id["fias-gar"]["cursor"]) == 'W/"etag"'
    assert str(by_id["geonames-ru"]["cursor"]) == "2026-09-08"


def test_check_json_skips_unchanged_and_error_cursors(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = _prepare_root(tmp_path)
    check_json = tmp_path / "check.json"
    check_json.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "ukase-326",
                        "changed": False,
                        "error": False,
                        "cursor_new": "noop-cursor",
                    },
                    {
                        "id": "fias-gar",
                        "changed": True,
                        "error": True,
                        "cursor_new": "error-cursor",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _patch_sync(monkeypatch, root, FakeSession(_geonames_handler("")))
    code = sync_mod.main(["--apply", "--check-json", str(check_json)])
    assert code == 0
    json.loads(capsys.readouterr().out)
    catalog = yaml.safe_load((root / "data/sources/catalog.yaml").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in catalog["sources"]}
    assert "cursor" not in by_id["ukase-326"] or by_id["ukase-326"].get("cursor") in (None, "")
    assert "cursor" not in by_id["fias-gar"]


def test_pointer_source_only_checked_at(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _prepare_root(tmp_path)
    _patch_sync(monkeypatch, root, FakeSession(_geonames_handler("")))
    cities_before = (root / "data/curated/cities-major.csv").read_bytes()
    code = sync_mod.main(["--source", "fias-gar", "--apply"])
    assert code == 0
    json.loads(capsys.readouterr().out)
    assert (root / "data/curated/cities-major.csv").read_bytes() == cities_before
    catalog = yaml.safe_load((root / "data/sources/catalog.yaml").read_text(encoding="utf-8"))
    row = next(s for s in catalog["sources"] if s["id"] == "fias-gar")
    assert str(row["checked_at"]) == "2026-09-09"


def test_vendor_true_too_large_exit_2(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _prepare_root(tmp_path)
    catalog_path = root / "data/sources/catalog.yaml"
    payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    payload["sources"].append(
        {
            "id": "huge-dump",
            "url": "https://example.invalid/dump.zip",
            "license": "CC-BY-4.0",
            "vendor": True,
            "max_vendor_bytes": 10485760,
            "checked_at": "2026-09-09",
            "detector": {"kind": "none"},
        }
    )
    catalog_path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")

    def handler(method: str, url: str, _kwargs: dict):
        return FakeResponse(headers={"Content-Length": "20971520"})

    _patch_sync(monkeypatch, root, FakeSession(handler))
    code = sync_mod.main(["--source", "huge-dump", "--apply"])
    assert code == 2
    err = capsys.readouterr().err
    assert "max_vendor_bytes" in err
    assert not list((root / "data").rglob("*.zip"))


def test_too_large_helper() -> None:
    assert too_large("10485761", 10485760) is True
    assert too_large("10485760", 10485760) is False
    assert too_large("", 10485760) is False


def test_write_csv_skips_unchanged(tmp_path: Path) -> None:
    header, rows = read_csv(FIXTURES / "places_two.csv")
    path = tmp_path / "out.csv"
    assert write_csv(path, header, rows) is True
    assert write_csv(path, header, rows) is False
