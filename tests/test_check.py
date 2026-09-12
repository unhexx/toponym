from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import requests
import yaml

import scripts.check as check_mod
from scripts.lib.catalog import load_catalog
from scripts.lib.detectors import (
    check_catalog,
    exit_code,
    expand_url,
    fingerprint_text,
    normalize_html,
    yesterday_utc,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXED_NOW = datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC)
DUMP_LM = "Tue, 08 Sep 2026 12:00:00 GMT"


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        text: str = "",
        headers: dict[str, str] | None = None,
        json_data=None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = headers or {}
        self._json = json_data
        self.ok = 200 <= status_code < 400
        self.raw = None

    def raise_for_status(self) -> None:
        if not self.ok:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        if self._json is not None:
            return self._json
        return json.loads(self.text or "null")

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


def _mods(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _geonames_handler(
    *,
    mods_body: str,
    deletes_body: str = "",
    dump_lm: str = DUMP_LM,
    mods_status: int = 200,
    deletes_status: int = 200,
    dump_status: int = 200,
):
    def handler(method: str, url: str, _kwargs: dict):
        if "modifications-" in url:
            return FakeResponse(mods_status, mods_body)
        if "deletes-" in url:
            return FakeResponse(deletes_status, deletes_body)
        if "RU.zip" in url:
            return FakeResponse(dump_status, "", headers={"Last-Modified": dump_lm})
        raise AssertionError(f"unexpected {method} {url}")

    return handler


def _write_catalog(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def _run_cli(monkeypatch, catalog_path: Path, argv: list[str], session: FakeSession | None):
    monkeypatch.setattr(check_mod, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(check_mod, "utcnow", lambda: FIXED_NOW)
    monkeypatch.setattr(check_mod, "build_session", lambda: session)
    return check_mod.main(argv)


def test_yesterday_is_utc_date() -> None:
    assert yesterday_utc(FIXED_NOW) == "2026-09-08"
    url = expand_url(
        "https://download.geonames.org/export/dump/modifications-{yesterday}.txt",
        now=FIXED_NOW,
    )
    assert url.endswith("modifications-2026-09-08.txt")


def test_non_ru_mods_exit_0(monkeypatch, capsys) -> None:
    catalog_path = FIXTURES / "catalog_check_geonames.yaml"
    session = FakeSession(_geonames_handler(mods_body=_mods("geonames_mods_non_ru.tsv")))
    code = _run_cli(monkeypatch, catalog_path, ["--json"], session)
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert code == 0
    assert report["changed_count"] == 0
    assert report["error_count"] == 0
    assert report["sources"][0]["changed"] is False
    assert report["sources"][0]["error"] is False
    assert "0 RU rows in mods" in report["sources"][0]["reason"]
    assert report["sources"][0]["cursor_new"] == "2026-09-08"
    assert any("modifications-2026-09-08.txt" in call["url"] for call in session.calls)
    assert not any("RU.zip" in call["url"] for call in session.calls)


def test_ru_mods_exit_10(monkeypatch, capsys) -> None:
    catalog_path = FIXTURES / "catalog_check_geonames.yaml"
    session = FakeSession(_geonames_handler(mods_body=_mods("geonames_mods_ru.tsv")))
    code = _run_cli(monkeypatch, catalog_path, ["--json"], session)
    report = json.loads(capsys.readouterr().out)
    assert code == 10
    assert report["changed_count"] == 1
    assert report["error_count"] == 0
    assert report["sources"][0]["changed"] is True
    assert "RU" in report["sources"][0]["reason"]
    assert report["sources"][0]["cursor_new"] == "2026-09-08"
    assert not any("RU.zip" in call["url"] for call in session.calls)


def test_offline_mixed_catalog_exit_2(monkeypatch, capsys) -> None:
    catalog_path = FIXTURES / "catalog_offline_mixed.yaml"
    code = _run_cli(monkeypatch, catalog_path, ["--json", "--offline"], session=None)
    report = json.loads(capsys.readouterr().out)
    assert code == 2
    assert report["error_count"] >= 1
    by_id = {row["id"]: row for row in report["sources"]}
    assert by_id["geonames-ru"]["error"] is True
    assert by_id["wikidata"]["changed"] is False
    assert by_id["wikidata"]["error"] is False


def test_offline_real_catalog_mixed_exit_2(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_mod, "utcnow", lambda: FIXED_NOW)
    code = check_mod.main(["--json", "--offline"])
    report = json.loads(capsys.readouterr().out)
    assert code == 2
    assert report["error_count"] >= 1


def test_offline_none_only_exit_0(monkeypatch, capsys) -> None:
    catalog_path = FIXTURES / "catalog_none_only.yaml"
    code = _run_cli(monkeypatch, catalog_path, ["--json", "--offline"], session=None)
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["changed_count"] == 0
    assert report["error_count"] == 0
    assert report["sources"][0]["changed"] is False
    assert report["sources"][0]["reason"] == "kind=none"


def test_kind_none_never_changed() -> None:
    catalog = load_catalog(FIXTURES / "catalog_none_only.yaml")
    report = check_catalog(catalog, offline=False, now=FIXED_NOW, session=None)
    assert report["changed_count"] == 0
    assert report["sources"][0]["changed"] is False


def test_http_timeout_exit_2(monkeypatch, capsys) -> None:
    def handler(method: str, url: str, _kwargs: dict):
        raise requests.Timeout("timed out")

    session = FakeSession(handler)
    code = _run_cli(
        monkeypatch,
        FIXTURES / "catalog_check_geonames.yaml",
        ["--json"],
        session,
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 2
    assert report["error_count"] >= 1
    assert report["sources"][0]["error"] is True
    assert report["sources"][0]["blocking"] is True


def test_pointer_http_head_timeout_nonblocking_exit_0(tmp_path: Path) -> None:
    catalog = {
        "updated": "2026-09-09",
        "sources": [
            {
                "id": "gkgn-opendata",
                "url": "https://rosreestr.gov.ru/opendata/example",
                "license": "official-open-data",
                "vendor": False,
                "checked_at": "2026-09-09",
                "detector": {
                    "kind": "http_head",
                    "urls": ["https://rosreestr.gov.ru/opendata/example"],
                },
            }
        ],
    }

    def handler(method: str, url: str, _kwargs: dict):
        raise requests.Timeout("timed out")

    report = check_catalog(catalog, session=FakeSession(handler), now=FIXED_NOW)
    assert exit_code(report) == 0
    assert report["error_count"] == 1
    assert report["sources"][0]["error"] is True
    assert report["sources"][0]["blocking"] is False
    assert report["sources"][0]["changed"] is False
    assert "pointer only" in report["sources"][0]["reason"]


def test_pointer_timeout_does_not_block_geonames_changed(tmp_path: Path) -> None:
    catalog = {
        "updated": "2026-09-09",
        "sources": [
            {
                "id": "gkgn-opendata",
                "url": "https://rosreestr.gov.ru/opendata/example",
                "license": "official-open-data",
                "vendor": False,
                "checked_at": "2026-09-09",
                "detector": {
                    "kind": "http_head",
                    "urls": ["https://rosreestr.gov.ru/opendata/example"],
                },
            },
            yaml.safe_load((FIXTURES / "catalog_check_geonames.yaml").read_text(encoding="utf-8"))[
                "sources"
            ][0],
        ],
    }

    def handler(method: str, url: str, _kwargs: dict):
        if "rosreestr" in url:
            raise requests.Timeout("timed out")
        if "modifications-" in url:
            return FakeResponse(200, _mods("geonames_mods_ru.tsv"))
        if "deletes-" in url:
            return FakeResponse(200, "")
        raise AssertionError(url)

    report = check_catalog(catalog, session=FakeSession(handler), now=FIXED_NOW)
    assert exit_code(report) == 10
    by_id = {row["id"]: row for row in report["sources"]}
    assert by_id["gkgn-opendata"]["error"] is True
    assert by_id["gkgn-opendata"]["blocking"] is False
    assert by_id["geonames-ru"]["changed"] is True
    assert by_id["geonames-ru"]["error"] is False


def test_github_sha_differs_exit_10(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = {
        "updated": "2026-09-09",
        "sources": [
            {
                "id": "hflabs-region",
                "url": "https://github.com/hflabs/region",
                "license": "CC-BY-SA-4.0",
                "vendor": False,
                "checked_at": "2026-09-09",
                "cursor": "oldsha",
                "detector": {
                    "kind": "github_commits",
                    "repo": "hflabs/region",
                    "since": "checked_at",
                },
            }
        ],
    }
    catalog_path = _write_catalog(tmp_path, payload)

    def handler(method: str, url: str, kwargs: dict):
        assert "api.github.com/repos/hflabs/region/commits" in url
        params = kwargs.get("params") or {}
        assert params.get("since") == "2026-09-09"
        return FakeResponse(json_data=[{"sha": "abc123deadbeef"}])

    session = FakeSession(handler)
    code = _run_cli(monkeypatch, catalog_path, ["--json"], session)
    report = json.loads(capsys.readouterr().out)
    assert code == 10
    assert report["sources"][0]["changed"] is True
    assert report["sources"][0]["cursor_new"] == "abc123deadbeef"


def test_github_no_commits_unchanged(tmp_path: Path) -> None:
    catalog = {
        "updated": "2026-09-09",
        "sources": [
            {
                "id": "hflabs-city",
                "url": "https://github.com/hflabs/city",
                "license": "CC-BY-SA-4.0",
                "vendor": False,
                "checked_at": "2026-09-09",
                "cursor": "same",
                "detector": {
                    "kind": "github_commits",
                    "repo": "hflabs/city",
                    "since": "checked_at",
                },
            }
        ],
    }

    def handler(method: str, url: str, _kwargs: dict):
        return FakeResponse(json_data=[])

    report = check_catalog(catalog, session=FakeSession(handler), now=FIXED_NOW)
    assert exit_code(report) == 0
    assert report["sources"][0]["changed"] is False


def test_http_head_etag_change(tmp_path: Path) -> None:
    catalog = {
        "updated": "2026-09-09",
        "sources": [
            {
                "id": "gkgn-opendata",
                "url": "https://example.invalid/gkgn",
                "license": "official-open-data",
                "vendor": False,
                "checked_at": "2026-09-09",
                "cursor": 'W/"old"',
                "detector": {"kind": "http_head", "urls": ["https://example.invalid/gkgn"]},
            }
        ],
    }

    def handler(method: str, url: str, _kwargs: dict):
        return FakeResponse(headers={"ETag": 'W/"new"', "Last-Modified": DUMP_LM})

    report = check_catalog(catalog, session=FakeSession(handler), now=FIXED_NOW)
    assert exit_code(report) == 10
    assert report["sources"][0]["changed"] is True


def test_page_fingerprint_stable() -> None:
    html_a = "<html><script>foo()</script><body>Hello   world</body></html>"
    html_b = "<html><style>p{}</style><body>Hello world</body></html>"
    assert fingerprint_text(normalize_html(html_a)) == fingerprint_text(normalize_html(html_b))


def test_json_shape_keys(monkeypatch, capsys) -> None:
    session = FakeSession(_geonames_handler(mods_body=_mods("geonames_mods_non_ru.tsv")))
    _run_cli(monkeypatch, FIXTURES / "catalog_check_geonames.yaml", ["--json"], session)
    report = json.loads(capsys.readouterr().out)
    assert set(report) >= {"as_of", "sources", "changed_count", "error_count"}
    row = report["sources"][0]
    assert set(row) >= {
        "id",
        "changed",
        "reason",
        "cursor_old",
        "cursor_new",
        "error",
        "blocking",
    }
    assert report["as_of"].endswith("Z")


def test_stamp_shifts_checked_at_without_network(tmp_path: Path, monkeypatch) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        (FIXTURES / "catalog_valid.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(check_mod, "CATALOG_PATH", catalog_path)

    def boom():
        raise AssertionError("network")

    monkeypatch.setattr(check_mod, "build_session", boom)
    code = check_mod.main(["--stamp", "--today", "2026-09-11"])
    assert code == 0
    payload = load_catalog(catalog_path)
    assert payload["updated"] == "2026-09-11"
    assert payload["sources"][0]["checked_at"] == "2026-09-11"


def test_stamp_defaults_today_to_utcnow(tmp_path: Path, monkeypatch) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        (FIXTURES / "catalog_valid.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(check_mod, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(check_mod, "utcnow", lambda: datetime(2026, 9, 12, 6, 0, 0, tzinfo=UTC))
    assert check_mod.main(["--stamp"]) == 0
    payload = load_catalog(catalog_path)
    assert payload["updated"] == "2026-09-12"
    assert payload["sources"][0]["checked_at"] == "2026-09-12"


def test_dump_last_modified_does_not_flip_changed(monkeypatch, capsys) -> None:
    session = FakeSession(
        _geonames_handler(
            mods_body=_mods("geonames_mods_non_ru.tsv"),
            dump_lm="Wed, 09 Sep 2026 01:00:00 GMT",
        )
    )
    code = _run_cli(
        monkeypatch,
        FIXTURES / "catalog_check_geonames.yaml",
        ["--json"],
        session,
    )
    report = json.loads(capsys.readouterr().out)
    row = report["sources"][0]
    assert code == 0
    assert report["changed_count"] == 0
    assert row["changed"] is False
    assert "0 RU rows in mods" in row["reason"]
    assert "Last-Modified" not in row["reason"]
    assert row["cursor_old"] == "2026-09-08"
    assert row["cursor_new"] == "2026-09-08"
    assert not any("RU.zip" in call["url"] for call in session.calls)
