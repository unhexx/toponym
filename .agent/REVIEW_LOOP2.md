## Summary

Loop 2 on `feature/P10-serve` matches DEC-SERVE-001: stdlib `scripts/serve.py` over existing FTS5, loopback CLI default `127.0.0.1:8099`, Compose one-shot `python:3.12-slim` with `validate → index → serve`, host publish `127.0.0.1:8099:8099`, and no FastAPI/Datasette/Agentix stack. `fts_match` is unchanged; phrase quoting, Волга/`wd:Q626` and МВД/`foiv:mvd` handler tests, file-contract tests (ports, `cap_drop: ALL`, `.dockerignore` excludes `agentic_loop_template`), and ontology `DEC-SERVE-001` are in place. Handler/contract tests in this worktree were green. Remaining gaps are contract edges, not a broken search path: non-POST writes never become JSON 405, search maps index failures to 400, 503-without-rebuild is only tested on `/healthz`, and the stdlib handler still logs the full query string and a `Server` header.

## Issues

### Issue 1 -- Severity: suggestion
- File: scripts/serve.py:235
- Description: GET-only is enforced only for methods that have `do_*` hooks (`GET`, `HEAD`, `POST`). `handle()` correctly returns 405 JSON with `Allow: GET` for POST, but `PUT` / `DELETE` / `PATCH` / `OPTIONS` never reach `handle()`: `BaseHTTPRequestHandler` answers `501` HTML (`Unsupported method`). Writes still fail, but the frozen JSON envelope (`method_not_allowed`) and `Allow: GET` do not apply to the other verbs.
- Suggestion: Add a single `do_*` fallback (or override `handle_one_request`) so every non-GET method except optional `HEAD /healthz` goes through `handle()` and returns 405 JSON. Tests should cover at least `PUT /v1/search`.
- Status: addressed

### Issue 2 -- Severity: suggestion
- File: scripts/serve.py:186
- Description: `/healthz` and `/v1/records` map `sqlite3.Error` to 503 `index_unavailable`. `/v1/search` maps both `sqlite3.OperationalError` and the broader `sqlite3.Error` to 400 `invalid_query`. A present but unreadable/corrupt/locked `registry.db` (file exists, so the `is_file()` guard passes) is therefore reported as a bad query rather than a missing index. MATCH syntax errors should stay 400; index-level failures should not.
- Suggestion: Keep 400 only for MATCH/FTS syntax (`OperationalError` whose message is query-related). Treat missing tables, I/O, and other `sqlite3.Error` like `/healthz` (503 `index_unavailable`).
- Status: addressed

### Issue 3 -- Severity: suggestion
- File: tests/test_serve.py:111
- Description: 503 `index_unavailable` is tested only for `GET /healthz` on a missing path. `_search` and `_record` have the same `is_file()` guard and must not call `rebuild_index`, but nothing asserts `GET /v1/search` / `GET /v1/records` return 503, or that the missing path is still absent afterwards. A later change that opened SQLite first would create an empty db (`sqlite3.connect` is R/W) and still look green.
- Suggestion: Add handler cases: missing db → 503 on `/v1/search` and `/v1/records`; after the call the path is not created; `rebuild_index` is not invoked.
- Status: addressed

### Issue 4 -- Severity: suggestion
- File: scripts/serve.py:226
- Description: `_dispatch` calls `self.send_response(response.status)`. Stdlib `send_response` logs `self.requestline` (full query string, including `q=`) via `log_request` → `log_message`, and injects `Server: BaseHTTP/… Python/…`. The loop 2 contract asked for one stderr line with path + status (not the raw `q`) and no `Server` stack header. `log_message` only redirects that default line to stderr; it does not strip the query.
- Suggestion: Use `send_response_only` (or a subclass that skips `log_request` / `version_string`) and log `path + status + q_len` yourself. Do not send a `Server` header.
- Status: addressed

### Issue 5 -- Severity: nit
- File: scripts/index.py:241
- Description: `fts_search`, `get_record`, and `index_counts` open `sqlite3.connect(db_path)` in the default read-write mode. Serve avoids rebuild, but it still *can* write or create a file if the `is_file()` check in `scripts/serve.py:155` is skipped or races. Opening URI `file:…?mode=ro` would make “serve must not rebuild” mechanical.
- Suggestion: Open the derived db read-only in the three serve-facing helpers (leave `fts_match` / `rebuild_index` as they are).
- Status: addressed

### Issue 6 -- Severity: nit
- File: tests/test_serve.py:69
- Description: `test_quoted_operators_never_500` allows 200 or 400 for `Волга AND Москва` and `МВД*`. That only proves no 500. Unquoted boolean `AND` against the current seeds would also return 200 with zero hits, so the case does not prove phrase wrapping. Unquoted `Волга OR МВД` would return both `wd:Q626` and `foiv:mvd`; quoted it must not.
- Suggestion: Assert `q=Волга OR МВД` is not a boolean OR (ids must not contain both hydronym and agency). Keep the `"` / `*` cases for “never 500”.
- Status: addressed
