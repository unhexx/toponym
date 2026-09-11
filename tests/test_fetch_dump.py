from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

import scripts.fetch_dump as fetch_mod
from scripts.fetch_dump import FetchError, assert_dest_outside_repo, fetch_dump, resolve_dump

ROOT = Path(__file__).resolve().parents[1]
CATALOG = yaml.safe_load((ROOT / "data" / "sources" / "catalog.yaml").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.closed = False

    def iter_content(self, chunk_size: int = 1):
        data = self.content
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[dict] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append({"method": method.upper(), "url": url, "kwargs": kwargs})
        return self.handler(method.upper(), url, kwargs)

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)


def test_source_md_present_for_raw_dirs() -> None:
    raw = ROOT / "data" / "raw"
    dirs = [path for path in raw.iterdir() if path.is_dir()]
    assert dirs
    for path in dirs:
        source_md = path / "SOURCE.md"
        assert source_md.is_file(), path.name
        text = source_md.read_text(encoding="utf-8")
        assert "Лицензия" in text or "лицензия" in text


def test_dump_source_md_forbids_git_vendor() -> None:
    for name, needle in (
        ("geonames-ru", "RU.zip"),
        ("fias-gar", "ГАР"),
        ("gkgn-opendata", "git"),
    ):
        text = (ROOT / "data" / "raw" / name / "SOURCE.md").read_text(encoding="utf-8")
        assert needle in text
        assert "fetch_dump.py" in text
        assert "--dest" in text or "вне" in text


def test_assert_dest_refuses_repo_and_data(tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="внутри репозитория"):
        assert_dest_outside_repo(ROOT, ROOT)
    with pytest.raises(FetchError, match="внутри репозитория"):
        assert_dest_outside_repo(ROOT / "data" / "raw" / "geonames-ru", ROOT)
    outside = tmp_path / "dumps"
    assert not fetch_mod.is_inside_repo(outside, ROOT)
    got = assert_dest_outside_repo(outside, ROOT)
    assert got == outside


def test_resolve_geonames_direct_and_pointers_need_url() -> None:
    by_id = {row["id"]: row for row in CATALOG["sources"]}
    url, name = resolve_dump(by_id["geonames-ru"], url_override=None)
    assert url.endswith("RU.zip")
    assert name == "RU.zip"
    with pytest.raises(FetchError, match="--url"):
        resolve_dump(by_id["fias-gar"], url_override=None)
    with pytest.raises(FetchError, match="--url"):
        resolve_dump(by_id["gkgn-opendata"], url_override=None)
    url, name = resolve_dump(by_id["fias-gar"], url_override="https://example.test/gar.7z")
    assert name == "gar.7z"
    with pytest.raises(FetchError, match="не дамп"):
        resolve_dump(by_id["wikidata"], url_override=None)


def test_fetch_refuses_dest_inside_repo(tmp_path: Path) -> None:
    code = fetch_mod.main(
        [
            "--source",
            "geonames-ru",
            "--dest",
            str(ROOT / "data" / "raw"),
            "--dry-run",
            "--root",
            str(ROOT),
        ]
    )
    assert code == 2
    code = fetch_mod.main(
        [
            "--source",
            "geonames-ru",
            "--dest",
            str(ROOT / "data" / "raw" / "geonames-ru"),
            "--root",
            str(ROOT),
        ]
    )
    assert code == 2
    assert not list((ROOT / "data" / "raw" / "geonames-ru").glob("*.zip"))


def test_fetch_geonames_writes_outside_repo(tmp_path: Path) -> None:
    dest = tmp_path / "outside"
    payload = b"PK\x03\x04fake-ru-zip"
    session = FakeSession(
        lambda method, url, kwargs: FakeResponse(content=payload if "RU.zip" in url else b"")
    )
    result = fetch_dump(
        source_id="geonames-ru",
        dest=dest,
        url=None,
        dry_run=False,
        root=ROOT,
        catalog=CATALOG,
        session=session,
    )
    written = Path(result["dest"])
    assert written == dest / "RU.zip"
    assert written.is_file()
    assert written.read_bytes() == payload
    assert result["bytes"] == len(payload)
    assert not fetch_mod.is_inside_repo(written, ROOT)
    assert not (ROOT / "data" / "raw" / "geonames-ru" / "RU.zip").exists()
    assert session.calls and session.calls[0]["kwargs"].get("stream") is True
    assert session.calls[0]["kwargs"].get("timeout") == fetch_mod.TIMEOUT_SEC


def test_fetch_dry_run_does_not_write(tmp_path: Path) -> None:
    dest = tmp_path / "dry"
    result = fetch_dump(
        source_id="geonames-ru",
        dest=dest,
        url=None,
        dry_run=True,
        root=ROOT,
        catalog=CATALOG,
        session=FakeSession(lambda *_: FakeResponse(status_code=500)),
    )
    assert result["dry_run"] is True
    assert result["bytes"] == 0
    assert not dest.exists()
    assert "RU.zip" in result["dest"]


def test_fetch_pointer_without_url_exits_2() -> None:
    code = fetch_mod.main(["--source", "fias-gar", "--root", str(ROOT)])
    assert code == 2
    code = fetch_mod.main(["--source", "gkgn-opendata", "--dry-run", "--root", str(ROOT)])
    assert code == 2


def test_fetch_pointer_with_url_outside(tmp_path: Path) -> None:
    dest = tmp_path / "gar"
    session = FakeSession(lambda method, url, kwargs: FakeResponse(content=b"gar-bytes"))
    result = fetch_dump(
        source_id="fias-gar",
        dest=dest,
        url="https://example.test/fias_delta.zip",
        dry_run=False,
        root=ROOT,
        catalog=CATALOG,
        session=session,
    )
    written = Path(result["dest"])
    assert written.name == "fias_delta.zip"
    assert written.read_bytes() == b"gar-bytes"
    assert not fetch_mod.is_inside_repo(written, ROOT)


def test_http_error_does_not_leave_repo_dump(tmp_path: Path) -> None:
    dest = tmp_path / "fail"
    session = FakeSession(lambda *_: FakeResponse(status_code=404, content=b"nope"))
    with pytest.raises(FetchError, match="HTTP 404"):
        fetch_dump(
            source_id="geonames-ru",
            dest=dest,
            url=None,
            dry_run=False,
            root=ROOT,
            catalog=CATALOG,
            session=session,
        )
    assert not (ROOT / "data" / "raw" / "geonames-ru" / "RU.zip").exists()
    assert not list(dest.glob("*")) if dest.exists() else True


def test_env_dest_still_refuses_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOPONYM_DUMP_DIR", str(ROOT / "data" / "raw"))
    with pytest.raises(FetchError, match="внутри репозитория"):
        fetch_dump(
            source_id="geonames-ru",
            dest=None,
            url=None,
            dry_run=True,
            root=ROOT,
            catalog=CATALOG,
        )
    monkeypatch.delenv("TOPONYM_DUMP_DIR", raising=False)
    assert os.environ.get("TOPONYM_DUMP_DIR") in (None, "")
