from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.index as index_mod
import scripts.serve as serve_mod
from scripts.serve import Request, handle

ROOT = Path(__file__).resolve().parents[1]


def _build(tmp_path: Path) -> Path:
    db_path = tmp_path / "registry.db"
    stats = index_mod.rebuild_index(ROOT, db_path)
    assert stats["records"] > 0
    return db_path


def _get(path: str, db_path: Path, **params: str) -> tuple[int, dict, dict]:
    query: dict[str, list[str]] = {key: [value] for key, value in params.items()}
    req = Request(method="GET", path=path, query=query)
    response = handle(req, db_path)
    payload = json.loads(response.body.decode("utf-8"))
    return response.status, response.headers, payload


def test_search_volga(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, headers, payload = _get("/v1/search", db_path, q="Волга")
    assert status == 200, payload
    assert "charset=utf-8" in headers["Content-Type"]
    assert payload["ok"] is True
    assert "wd:Q626" in payload["ids"]
    hit = next(row for row in payload["hits"] if row["id"] == "wd:Q626")
    assert hit["table_name"] == "hydronyms-major"
    assert hit["name_ru"] == "Волга"
    raw = handle(Request("GET", "/v1/search", {"q": ["Волга"]}), db_path).body
    assert "Волга".encode() in raw
    assert b"\\u0412" not in raw


def test_search_mvd(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/search", db_path, q="МВД")
    assert status == 200, payload
    assert "foiv:mvd" in payload["ids"]


def test_search_tverskoy_lemma_alias(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/search", db_path, q="Тверской")
    assert status == 200, payload
    assert "wd:Q1644209" in payload["ids"]
    hit = next(row for row in payload["hits"] if row["id"] == "wd:Q1644209")
    assert hit["name_ru"] == "Тверская улица"
    assert hit["table_name"] == "hodonyms"
    assert "lemma" not in hit
    assert "gen" not in hit


def test_missing_and_empty_query(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/search", db_path)
    assert status == 400
    assert payload["error"] == "missing_query"
    status, _headers, payload = _get("/v1/search", db_path, q="   ")
    assert status == 400
    assert payload["error"] == "missing_query"


def test_query_too_long(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/search", db_path, q="а" * 201)
    assert status == 400
    assert payload["error"] == "query_too_long"


def test_quoted_operators_never_500(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    for q in ('Волга AND Москва', 'foo"', "МВД*", '""'):
        status, _headers, payload = _get("/v1/search", db_path, q=q)
        assert status in {200, 400}, (q, payload)
        if status == 400:
            assert payload["error"] in {"invalid_query", "missing_query", "query_too_long"}
    status, _headers, payload = _get("/v1/search", db_path, q="Волга OR МВД")
    assert status == 200, payload
    ids = set(payload["ids"])
    assert not ({"wd:Q626", "foiv:mvd"} <= ids)


def test_invalid_limit(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    for limit in ("0", "101", "abc"):
        status, _headers, payload = _get("/v1/search", db_path, q="Волга", limit=limit)
        assert status == 400, payload
        assert payload["error"] == "invalid_limit"


def test_record_lookup(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/records", db_path, id="wd:Q626")
    assert status == 200, payload
    assert payload["hit"]["id"] == "wd:Q626"


def test_record_card_includes_coord_number(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/records", db_path, id="wd:Q649")
    assert status == 200, payload
    hit = payload["hit"]
    assert isinstance(hit["lat"], float)
    assert isinstance(hit["lon"], float)
    assert 55.0 < hit["lat"] < 56.0
    assert hit["oktmo"] == "45000000"
    assert "fias" in hit
    status, _headers, search = _get("/v1/search", db_path, q="Москва")
    assert status == 200
    card = next(row for row in search["hits"] if row["id"] == "wd:Q649")
    assert isinstance(card["lat"], float)
    status, _headers, payload = _get("/v1/records", db_path, id="no-such-id")
    assert status == 404
    assert payload["error"] == "not_found"
    status, _headers, payload = _get("/v1/records", db_path)
    assert status == 400
    assert payload["error"] == "missing_id"


def test_declensions_moscow(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/declensions", db_path, id="wd:Q649")
    assert status == 200, payload
    assert payload["ok"] is True
    assert payload["count"] == 1
    hit = payload["hits"][0]
    assert hit["id"] == "wd:Q649"
    assert hit["lemma"] == "Москва"
    assert hit["gen"] == "Москвы"
    assert "nom" in hit and "pre" in hit
    assert "loc2" in hit
    assert hit["table_name"] == "cities-major"
    search_status, _h, search = _get("/v1/search", db_path, q="Москва")
    assert search_status == 200
    card = next(row for row in search["hits"] if row["id"] == "wd:Q649")
    assert "gen" not in card


def test_declensions_mvd_two_lemmas(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/declensions", db_path, id="foiv:mvd")
    assert status == 200, payload
    lemmas = {row["lemma"] for row in payload["hits"]}
    assert lemmas == {"МВД", "Министерство внутренних дел"}
    keys = [(row["id"], row["lemma"]) for row in payload["hits"]]
    assert len(keys) == len(set(keys))
    assert payload["count"] == 2


def test_declensions_unknown_and_missing(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/v1/declensions", db_path, id="no-such-id")
    assert status == 404
    assert payload["error"] == "not_found"
    status, _headers, payload = _get("/v1/declensions", db_path)
    assert status == 400
    assert payload["error"] == "missing_id"
    missing = tmp_path / "missing.db"
    status, _headers, payload = _get("/v1/declensions", missing, id="wd:Q649")
    assert status == 200, payload
    assert payload["hits"][0]["gen"] == "Москвы"


def test_unknown_path_and_post(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/nope", db_path)
    assert status == 404
    for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS"):
        req = Request(method=method, path="/v1/search", query={"q": ["Волга"]})
        response = handle(req, db_path)
        payload = json.loads(response.body.decode("utf-8"))
        assert response.status == 405, method
        assert payload["error"] == "method_not_allowed"
        assert response.headers.get("Allow") == "GET"


def test_healthz(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    status, _headers, payload = _get("/healthz", missing)
    assert status == 503
    assert payload["error"] == "index_unavailable"
    status, _headers, payload = _get("/v1/search", missing, q="Волга")
    assert status == 503
    assert payload["error"] == "index_unavailable"
    status, _headers, payload = _get("/v1/records", missing, id="wd:Q626")
    assert status == 503
    assert payload["error"] == "index_unavailable"
    assert not missing.exists()
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/healthz", db_path)
    assert status == 200
    assert payload["ok"] is True
    assert payload["records"] > 0
    assert payload["name"] == "toponym"
    assert payload["version"] == serve_mod.PACKAGE_VERSION
    assert payload["version"] == "2026.09.15"


def test_parse_args_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOPONYM_BIND", raising=False)
    monkeypatch.delenv("TOPONYM_PORT", raising=False)
    monkeypatch.delenv("TOPONYM_ALLOW_NON_LOOPBACK", raising=False)
    args = serve_mod.parse_args([])
    assert args.bind == "127.0.0.1"
    assert args.port == 8099


def test_main_refuses_non_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOPONYM_ALLOW_NON_LOOPBACK", raising=False)
    code = serve_mod.main(["--bind", "0.0.0.0"])
    assert code == 2


def test_root_discovery(tmp_path: Path) -> None:
    db_path = _build(tmp_path)
    status, _headers, payload = _get("/", db_path)
    assert status == 200
    assert "/v1/search" in payload["endpoints"]
    assert "/v1/declensions" in payload["endpoints"]
