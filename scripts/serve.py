#!/usr/bin/env python3
"""Loopback JSON API над derived SQLite FTS5."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.index import DEFAULT_OUT, ROOT, fts_search, get_record, index_counts  # noqa: E402
from scripts.lib.declensions import rows_for_id  # noqa: E402

PACKAGE_VERSION = "2026.09.09"
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8099
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_QUERY_CHARS = 200
JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
}


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    query: dict[str, list[str]]


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    env_bind = os.environ.get("TOPONYM_BIND") or DEFAULT_BIND
    env_port = os.environ.get("TOPONYM_PORT") or str(DEFAULT_PORT)
    env_db = os.environ.get("TOPONYM_DB") or str(DEFAULT_OUT)
    env_root = os.environ.get("TOPONYM_ROOT") or str(ROOT)
    env_allow = os.environ.get("TOPONYM_ALLOW_NON_LOOPBACK", "")
    parser = argparse.ArgumentParser(description="Loopback JSON-поиск по индексу toponym")
    parser.add_argument("--bind", default=env_bind, help="адрес bind (по умолчанию 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(env_port))
    parser.add_argument("--db", default=env_db, help="путь к registry.db")
    parser.add_argument("--root", default=env_root, help="корень канона")
    parser.add_argument(
        "--allow-non-loopback",
        action="store_true",
        default=_env_flag(env_allow),
        help="разрешить 0.0.0.0 внутри контейнера; compose публикует loopback",
    )
    return parser.parse_args(argv)


def _env_flag(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _json_response(payload: dict[str, Any], status: int) -> Response:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    headers = dict(JSON_HEADERS)
    headers["Content-Length"] = str(len(body))
    return Response(status=status, headers=headers, body=body)


def _error(status: int, code: str, message: str) -> Response:
    return _json_response({"ok": False, "error": code, "message": message}, status)


def _first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or []
    if not values:
        return ""
    return values[-1]


def _phrase_match(raw: str) -> str:
    escaped = raw.replace('"', '""')
    return f'"{escaped}"'


def _is_loopback(bind: str) -> bool:
    if bind in {"127.0.0.1", "localhost"}:
        return True
    if bind.startswith("127."):
        parts = bind.split(".")
        if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return True
    return False


def handle(req: Request, db_path: Path, *, root: Path | None = None) -> Response:
    canon = Path(root) if root is not None else ROOT
    method = req.method.upper()
    if method == "HEAD" and req.path == "/healthz":
        response = _healthz(db_path)
        return Response(status=response.status, headers=response.headers, body=b"")
    if method != "GET":
        response = _error(405, "method_not_allowed", "только GET")
        headers = dict(response.headers)
        headers["Allow"] = "GET"
        return Response(status=405, headers=headers, body=response.body)
    if req.path == "/":
        return _json_response(
            {
                "ok": True,
                "name": "toponym",
                "version": PACKAGE_VERSION,
                "endpoints": ["/healthz", "/v1/search", "/v1/records", "/v1/declensions"],
            },
            200,
        )
    if req.path == "/healthz":
        return _healthz(db_path)
    if req.path == "/v1/search":
        return _search(req, db_path)
    if req.path == "/v1/records":
        return _record(req, db_path)
    if req.path == "/v1/declensions":
        return _declensions(req, canon)
    return _error(404, "not_found", "нет такого пути")


def _healthz(db_path: Path) -> Response:
    if not db_path.is_file():
        return _error(503, "index_unavailable", "registry db missing or unreadable")
    try:
        counts = index_counts(db_path)
    except sqlite3.Error:
        return _error(503, "index_unavailable", "registry db missing or unreadable")
    return _json_response(
        {
            "ok": True,
            "name": "toponym",
            "version": PACKAGE_VERSION,
            "records": counts["records"],
            "sources": counts["sources"],
        },
        200,
    )


def _search(req: Request, db_path: Path) -> Response:
    if not db_path.is_file():
        return _error(503, "index_unavailable", "registry db missing or unreadable")
    raw = _first(req.query, "q").strip()
    if not raw:
        return _error(400, "missing_query", "нужен параметр q")
    if len(raw) > MAX_QUERY_CHARS:
        return _error(400, "query_too_long", f"q длиннее {MAX_QUERY_CHARS} символов")
    limit_raw = _first(req.query, "limit").strip()
    if not limit_raw:
        limit = DEFAULT_LIMIT
    else:
        try:
            limit = int(limit_raw)
        except ValueError:
            return _error(400, "invalid_limit", "limit должен быть целым")
        if limit < 1 or limit > MAX_LIMIT:
            return _error(400, "invalid_limit", "limit должен быть от 1 до 100")
    status_raw = (_first(req.query, "status") or "all").strip() or "all"
    if status_raw not in {"all", "active", "deprecated"}:
        return _error(400, "invalid_status", "status: all|active|deprecated")
    status = None if status_raw == "all" else status_raw
    table_name = _first(req.query, "table_name").strip() or None
    match = _phrase_match(raw)
    try:
        hits = fts_search(
            db_path,
            match,
            limit=limit,
            status=status,
            table_name=table_name,
        )
    except sqlite3.OperationalError as exc:
        return _error(400, "invalid_query", str(exc))
    except sqlite3.Error as exc:
        return _error(503, "index_unavailable", str(exc))
    ids = [row["id"] for row in hits]
    return _json_response(
        {"ok": True, "query": raw, "count": len(hits), "limit": limit, "ids": ids, "hits": hits},
        200,
    )


def _record(req: Request, db_path: Path) -> Response:
    if not db_path.is_file():
        return _error(503, "index_unavailable", "registry db missing or unreadable")
    record_id = _first(req.query, "id").strip()
    if not record_id:
        return _error(400, "missing_id", "нужен параметр id")
    try:
        hit = get_record(db_path, record_id)
    except sqlite3.Error as exc:
        return _error(503, "index_unavailable", str(exc))
    if hit is None:
        return _error(404, "not_found", "id not in index")
    return _json_response({"ok": True, "hit": hit}, 200)


def _declensions(req: Request, root: Path) -> Response:
    record_id = _first(req.query, "id").strip()
    if not record_id:
        return _error(400, "missing_id", "нужен параметр id")
    hits = rows_for_id(root, record_id)
    if not hits:
        return _error(404, "not_found", "id not in declensions")
    return _json_response(
        {"ok": True, "id": record_id, "count": len(hits), "hits": hits},
        200,
    )


class RegistryHandler(BaseHTTPRequestHandler):
    db_path: Path = DEFAULT_OUT
    root_path: Path = ROOT

    def version_string(self) -> str:
        return "toponym"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def log_request(self, code: object = "-", size: object = "-") -> None:
        path = urlparse(self.path).path
        q_len = len(urlparse(self.path).query)
        self.log_message('"%s %s" %s q_len=%s', self.command, path, str(code), q_len)

    def send_response(self, code: int, message: str | None = None) -> None:
        self.log_request(code)
        self.send_response_only(code, message)
        self.send_header("Date", self.date_time_string())

    def _dispatch(self) -> None:
        parsed = urlparse(self.path)
        req = Request(
            method=self.command,
            path=parsed.path,
            query=parse_qs(parsed.query, keep_blank_values=True),
        )
        response = handle(req, self.db_path, root=self.root_path)
        self.send_response(response.status)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD" and response.body:
            self.wfile.write(response.body)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch()

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch()

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._dispatch()


def make_handler(db_path: Path, root: Path | None = None) -> type[RegistryHandler]:
    class BoundHandler(RegistryHandler):
        pass

    BoundHandler.db_path = db_path
    BoundHandler.root_path = root or ROOT
    return BoundHandler


def serve(bind: str, port: int, db_path: Path, root: Path | None = None) -> None:
    handler = make_handler(db_path, root=root)
    httpd = ThreadingHTTPServer((bind, port), handler)
    httpd.daemon_threads = True

    def _stop(_signum: int, _frame: object) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    print(f"ok serve http://{bind}:{port}/healthz db={db_path}", flush=True)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except (argparse.ArgumentError, SystemExit, ValueError) as exc:
        if isinstance(exc, SystemExit):
            return int(exc.code or 2)
        print(str(exc), file=sys.stderr)
        return 2
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = Path(args.root) / db_path
    if not _is_loopback(args.bind) and not args.allow_non_loopback:
        print(
            "отказ: bind только 127.0.0.1 (для 0.0.0.0 передайте --allow-non-loopback)",
            file=sys.stderr,
        )
        return 2
    try:
        serve(args.bind, args.port, db_path, root=Path(args.root))
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
