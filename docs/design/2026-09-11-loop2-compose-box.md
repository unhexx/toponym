# Toponym Loop 2 — Compose install box + loopback search

Living snapshot of DEC-SERVE-001. Executable plan: `CYCLE_PLAN.md`. Do not keep a parallel SSOT only under `.agent/`.

| Field | Value |
|---|---|
| **Document** | MVP design for loop 2 (post-v1) |
| **Date** | 2026-09-11 |
| **Status** | Released — tag `2026.09.11` (P10–P15 landed) |
| **CalVer** | Loop 2 is `2026.09.11`. v1 remains `2026.09.09`. |
| **ADR parent** | `LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md` DEC-REG-001; new overlay decision `DEC-SERVE-001` |
| **Executable plan** | `CYCLE_PLAN.md` (Loop 2 table P10–P15 COMPLETE) |

This brief is the SSOT for loop 2. v1 (`docs/design/2026-09-09-v1-local-registries.md`, tag `2026.09.09`) is frozen. Do not reopen P0–P9. Do not rewrite CSV canon, detectors, or FTS schema.

Coder constraints (same as v1): one INVEST slice per cycle; merge + push `main` after Reviewer DONE; conventional commits in natural Russian; never mention models/agents/LLM; no empty commit; no `agentic_loop_template` tree copy.

---

## 1. Goal

Ship a **one-shot Docker Compose install box** that:

1. Pins **Python 3.12** (CI already does; the operator host currently has 3.14 only).
2. Installs product dependencies from `pyproject.toml` (no new runtime deps).
3. On start: **validate → index → serve**.
4. Exposes a **loopback JSON search** over the existing SQLite FTS5 (`knowledge/registry.db`).
5. Does **not** become a public API, a data portal, or the Agentix operator stack.

Success for an operator on a machine with Docker:

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
docker compose up --build
# other terminal:
curl -sG 'http://127.0.0.1:8099/v1/search' --data-urlencode 'q=Волга'
curl -sG 'http://127.0.0.1:8099/v1/search' --data-urlencode 'q=МВД'
```

Host path from README v1 (`bash Agent-Init.sh` + `.venv`) stays valid. The box is an **additional** install path, not a replacement of the CSV canon.

---

## 2. Hard constraints (do not violate)

From `AGENTS.md` / `TASK_SPECIFICATION.md` / v1 design:

- Canon remains git UTF-8 CSV (Frictionless). SQLite FTS stays **derived** and gitignored.
- Do not vendor dumps >10 MB or full ГАР/ФИАС. Do not copy `RU.zip` into the image.
- CC BY-SA / ODbL stay in `data/raw/`. Image may COPY `data/raw/*/SOURCE.md` (tiny pointers); never hflabs tables.
- CSV patch by stable id; no deletes (`status=deprecated`). Serve is **read-only** (no POST/PUT/DELETE).
- Python 3.12+, pytest, ruff. `requires-python = ">=3.12"` unchanged. No FastAPI/uvicorn/datasette in `pyproject.toml`.
- Do **not** copy `agentic_loop_template` into the product or into the image (`.dockerignore` must exclude it). Sibling symlink SSOT only.
- **pxpipe stays on the host.** Product compose must not publish **`:8100` / `:8110` / `:8112`**.
- Agentix operator stack (SearXNG `:8080`, LDR `:5000`, Ollama) is **not** the product. Do not mix those services into toponym’s default compose. Do not name the compose project `agentix`.
- Daily pipeline (`check.py` → `sync.py` → `validate.py` → `index.py`) stays on host/CI. The box does **not** run `check.py` or `sync.py` (network detectors would flake start).
- Do not bind the host publish address to `0.0.0.0`. Host publish is `127.0.0.1:8099:8099`.

Reserved ports (never steal):

| Port | Owner | Product compose |
|---|---|---|
| 8080 | Agentix SearXNG | MUST NOT |
| 8100 | host pxpipe | MUST NOT |
| 8110 | Agentix gateway | MUST NOT |
| 8112 | Agentix dashboard | MUST NOT |
| 5000 | Agentix LDR (profile) | MUST NOT |
| 11434 | Ollama (unpublished on host) | MUST NOT |
| **8099** | **toponym serve** | **YES, `127.0.0.1` only** |

---

## 3. Options compared

ADR §7 already sketched “thin `scripts/serve.py` loopback later”. Loop 2 is that later, plus a compose box so the operator is not blocked on host CPython 3.14.

| Option | What it would be | Verdict |
|---|---|---|
| **A. stdlib HTTP `scripts/serve.py` + one-service Compose** | `http.server` + existing `rebuild_index` / `fts_match`; image `python:3.12-slim`; compose publishes `127.0.0.1:8099` | **CHOSEN** |
| B. Datasette on `registry.db` | Instant SQL/JSON/HTML explorer; extra runtime dep; portal UX; hard to keep 3 endpoints and validate-first entrypoint | Rejected |
| C. FastAPI + uvicorn | Typed OpenAPI; Agentix dashboard uses it **in the template**, not in this product; pulls starlette/pydantic/uvicorn | Rejected |
| D. DuckDB HTTP / `read_csv_auto` as the service | CSV is already the canon; would duplicate FTS5; still needs a server; DEC-REG-001 rejected DuckDB as canon | Rejected |
| E. CKAN / Dataverse | PostgreSQL + Solr + catalog UI | Rejected (DEC-REG-001 §2.1 C: not local-first, excess) |
| F. Include Agentix compose (SearXNG/LDR/Ollama) | “All dependencies” misread as the operator research stack | Rejected (operator: not the product; port theft) |

### 3.1 Why A (stdlib + one-service box)

- Matches ADR §7 and v1 non-goal wording: *thin loopback*, not a public API.
- Zero new runtime dependencies. Recommended stack in `AGENTS.md` stays intact (no ADR needed for a new library).
- Handler is a pure function → pytest without a daemon.
- Docker image supplies CPython 3.12 matching `.github/workflows/ci.yml`.
- FTS5 already answers the acceptance queries «Волга» / «МВД» (`tests/test_index.py`). Serve is a JSON wrapper, not a second index.
- Image COPY of in-git canon is small (seeds, not dumps). Rebuild of FTS on start is sub-second for current row counts.

### 3.2 Rejected alternatives — why, in enough detail for a later ADR

**B. Datasette.** Excellent for publishing a SQLite file, and FTS5 tables show up. It is the wrong shape: HTML UI + arbitrary SQL + plugin ecosystem; default mental model is a *public data browser*. Constraining it to `/v1/search` plus a validate-first entrypoint is more work than writing 150 lines of stdlib HTTP. Adding `datasette` to `pyproject.toml` violates “do not deviate without an ADR”. License (Apache-2.0) is fine; the dependency and attack surface are not.

**C. FastAPI.** The template dashboard (`agentic_loop_template/memory/dashboard/server.py`) is FastAPI bound to `:8112`. Copying that pattern into the **product** would (1) add uvicorn/pydantic, (2) invite someone to publish OpenAPI on a non-loopback bind, (3) blur product vs harness. Loopback search does not need request models or WebSockets. `TestClient` would also add httpx to tests. Stdlib handler tests are enough.

**D. DuckDB.** ADR §2.1 A / v1 design alternative A already rejected DuckDB/SQLite *as canon* (poor git diffs). Loop 2 must not grow a second derived store. DuckDB does not remove the need for an HTTP process. `duckdb.read_csv_auto('data/curated/regions.csv')` remains a **consumer** recipe in README, not a server.

**E. CKAN.** Catalog-server with PostgreSQL/Solr. DEC-REG-001 rejected it. Ops cost dwarfs the seed registry. Would force vendoring or fetching dumps. Out.

**F. Agentix stack in product compose.** Template `deploy/compose.yaml` is named `agentix` and publishes `127.0.0.1:8080` (SearXNG). Operator instruction: pxpipe stays on the host; product compose must not steal `:8100/:8110/:8112`; SearXNG/LDR/Ollama are not the product. A toponym clone that `docker compose up`s Ollama would also violate “do not vendor huge blobs”. **Do not copy `agentic_loop_template/deploy/`.** Product compose is a sibling contract, not a fork of the template stack.

**Also rejected (smaller):**

- Binding serve to `:8000` or `:8080` — collision with common local servers / SearXNG.
- `network_mode: host` — bypasses `127.0.0.1` publish and can steal Agentix ports.
- Running `check.py`/`sync.py` in the container entrypoint — start would depend on GeoNames/GitHub and exit 10/2.
- Editable install + bind-mount of the whole repo as the default — host `.venv` and the template symlink would leak into the container. Default image is self-contained; live-mount is out of loop 2.
- HTML UI, CORS `*`, POST writeback, SPARQL, GeoJSON tiles — public-API creep.

---

## 4. Chosen architecture

```text
git canon (CSV) ──► validate.py ──► index.py ──► knowledge/registry.db (FTS5)
                                                      │
                                                      ▼
                                            scripts/serve.py (stdlib HTTP)
                                                      │
                                                      ▼
                                      127.0.0.1:8099  GET /v1/search?q=

Docker: python:3.12-slim image copies canon + scripts, pip install .
Compose: one service `toponym`, host publish 127.0.0.1:8099:8099
Entrypoint: validate → index → exec serve (bind 0.0.0.0 *inside* the container)
```

Canon stays files. Serve never writes CSV. Index rebuilds from scratch on every container start (current corpus is tiny; always consistent with the image).

Host without Docker (unchanged v1, plus serve):

```bash
python scripts/validate.py
python scripts/index.py
python scripts/serve.py          # binds 127.0.0.1:8099, refuses 0.0.0.0 unless flagged
```

---

## 5. HTTP JSON contract (normative)

Loopback search is **read-only JSON**. No HTML. No CORS headers. No cookies. No auth (loopback is the authz).

### 5.1 Bind

| Context | Bind address | Port |
|---|---|---|
| Host CLI default | `127.0.0.1` | `8099` |
| Inside Compose container | `0.0.0.0` (env) | `8099` |
| Host publish (compose `ports`) | `127.0.0.1:8099:8099` | |

CLI must **exit 2** if `--bind` is not a loopback address (`127.0.0.1`, `127.0.0.0/8`, `localhost`) unless `--allow-non-loopback` or `TOPONYM_ALLOW_NON_LOOPBACK=1`. Compose sets that env. Document that this flag is for container NAT, not for LAN serving.

IPv6 `::1` is out of loop 2 (do not bind dual-stack).

### 5.2 Endpoints

All paths are exact. Unknown path → `404`. Non-GET (except optional HEAD on `/healthz`) → `405` with `Allow: GET`.

#### `GET /healthz`

Liveness + index presence. Used by Compose healthcheck. Does not run FTS.

**200**

```json
{
  "ok": true,
  "name": "toponym",
  "version": "2026.09.11",
  "records": 447,
  "sources": 10
}
```

`records` / `sources` from `SELECT COUNT(*)` on `records` and `sync_meta`. `version` follows package CalVer (`pyproject.toml`; tagged `2026.09.11`).

**503** if the DB file is missing or `records` cannot be read:

```json
{
  "ok": false,
  "error": "index_unavailable",
  "message": "registry db missing or unreadable"
}
```

#### `GET /v1/search`

Query parameters:

| Param | Required | Default | Rules |
|---|---|---|---|
| `q` | yes | — | stripped; 1–200 Unicode chars; empty → 400 `missing_query` |
| `limit` | no | `20` | integer 1–100; invalid → 400 `invalid_limit` |
| `status` | no | `all` | `all` \| `active` \| `deprecated` |
| `table_name` | no | (any) | exact match on `records.table_name` (e.g. `hydronyms-major`) |

FTS query construction: wrap the user string as an FTS5 phrase so operators in the input cannot change MATCH meaning:

```text
escaped = q.replace('"', '""')
match   = '"' + escaped + '"'
```

Then `fts_search(db, match, limit=..., status=..., table_name=...)`. Do **not** pass raw `q` to MATCH.

On `sqlite3.OperationalError` from MATCH → 400 `invalid_query` (do not 500).

**200** (shape is frozen; extra keys forbidden in tests)

```json
{
  "ok": true,
  "query": "Волга",
  "count": 1,
  "limit": 20,
  "ids": ["wd:Q626"],
  "hits": [
    {
      "id": "wd:Q626",
      "table_name": "hydronyms-major",
      "type_id": "potamonym",
      "name_ru": "Волга",
      "name_yo": "",
      "name_en": "Volga",
      "abbr": "",
      "parent_id": "",
      "admin1": "",
      "wd": "Q626",
      "geonames": "472776",
      "iso": "",
      "status": "active",
      "source_id": "wikidata"
    }
  ]
}
```

`hits[]` keys = `scripts/index.py` `RECORD_FIELDS` (do not add `lat`/`lon`; they are not in the FTS records table). `ids` is the list of `hits[].id` in the same order (compat with `fts_match`).

Acceptance (must hold on the real canon index):

- `q=Волга` → `wd:Q626` in `ids`; that hit `table_name=hydronyms-major`
- `q=МВД` → `foiv:mvd` in `ids`

Zero hits → 200 with `count: 0`, `ids: []`, `hits: []` (not 404).

#### `GET /v1/records?id=wd:Q626`

Lookup by stable id (query param, not path, because ids contain `:`).

**200** `{ "ok": true, "hit": { …same fields as hits[]… } }`

**400** missing/empty `id` → `missing_id`

**404** `{ "ok": false, "error": "not_found", "message": "id not in index" }`

#### `GET /`

Discovery JSON so a human hitting the port is not confused:

```json
{
  "ok": true,
  "name": "toponym",
  "version": "2026.09.11",
  "endpoints": ["/healthz", "/v1/search", "/v1/records"]
}
```

### 5.3 Headers (every JSON response)

```
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
```

Body: `json.dumps(..., ensure_ascii=False, separators=(",", ":"))` plus trailing newline. UTF-8 bytes.

No `Access-Control-Allow-Origin`. No `Server:` advertising a stack. Do not log full query strings at INFO; one stderr line per request with status + path is enough (`search q_len=5 status=200`).

### 5.4 Error envelope

```json
{"ok": false, "error": "<code>", "message": "<human>"}
```

| HTTP | `error` |
|---|---|
| 400 | `missing_query` `invalid_limit` `invalid_status` `invalid_query` `missing_id` `query_too_long` |
| 404 | `not_found` |
| 405 | `method_not_allowed` |
| 503 | `index_unavailable` |

---

## 6. `scripts/serve.py` + index helper

### 6.1 Public functions (testable without a socket)

Follow the CLI bootstrap used by `check.py` / `index.py` (`_ROOT` on `sys.path`, `from scripts.lib…`).

```python
@dataclass(frozen=True)
class Request:
    method: str
    path: str                 # URL path only, no query
    query: dict[str, list[str]]  # urllib.parse.parse_qs

@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes
```

Normative API:

- `handle(req: Request, db_path: Path) -> Response` — no `HTTPServer`.
- `parse_args(argv) -> Namespace` — `--bind` (default `127.0.0.1`), `--port` (default `8099`), `--db` (default `knowledge/registry.db`), `--root`, `--allow-non-loopback`.
- `main(argv) -> int` — bind + serve forever; return 2 on bind/config error.

`http.server.BaseHTTPRequestHandler` (or a tiny subclass) translates socket → `Request` → `handle` → write. Use `socketserver.ThreadingMixIn` + `HTTPServer`, `daemon_threads = True`. Handle `SIGTERM`/`SIGINT` by `server.shutdown()` so Compose stop is clean (`init: true` in compose also reaps).

Do **not** use Flask/FastAPI. Do **not** import `memory.*` from the template.

### 6.2 Index helper

Keep `fts_match(db_path, query) -> list[str]` **byte-for-byte behaviour** (existing `tests/test_index.py`).

Add alongside in `scripts/index.py`:

```python
def fts_search(
    db_path: Path,
    query: str,
    *,
    limit: int = 20,
    status: str | None = None,
    table_name: str | None = None,
) -> list[dict[str, str]]:
    ...
```

SQL (bind parameters only):

```sql
SELECT r.id, r.table_name, r.type_id, r.name_ru, r.name_yo, r.name_en, r.abbr,
       r.parent_id, r.admin1, r.wd, r.geonames, r.iso, r.status, r.source_id
FROM records_fts AS f
JOIN records AS r ON r.rowid = f.rowid
WHERE records_fts MATCH ?
  AND (? IS NULL OR r.status = ?)
  AND (? IS NULL OR r.table_name = ?)
LIMIT ?
```

`status="all"` → pass NULL for the status predicates. `query` here is the already-quoted MATCH string from serve.

Do not change `SCHEMA_SQL`. Do not switch to external-content FTS; v1 landed manual `INSERT INTO records_fts` (design doc’s trigger sketch was not what P6 shipped — do not “fix” it in loop 2).

### 6.3 CLI env overlay

| Env | CLI | Default | Notes |
|---|---|---|---|
| `TOPONYM_BIND` | `--bind` | `127.0.0.1` | Container sets `0.0.0.0` |
| `TOPONYM_PORT` | `--port` | `8099` | |
| `TOPONYM_DB` | `--db` | `<root>/knowledge/registry.db` | Container: `/app/knowledge/registry.db` |
| `TOPONYM_ROOT` | `--root` | repo root of `serve.py` | |
| `TOPONYM_ALLOW_NON_LOOPBACK` | `--allow-non-loopback` | unset | `"1"` / `"true"` |

CLI flag wins over env. Invalid port → exit 2.

---

## 7. Compose contract (normative)

Root files (discoverable `docker compose up`):

- `compose.yaml` — product box (project name `toponym`)
- `Dockerfile` — `python:3.12-slim`
- `.dockerignore` — must exclude the template and dumps
- `scripts/entrypoint.sh` — validate → index → exec serve

Do **not** use `deploy/compose.yaml` (that path in the template is the Agentix stack). Do **not** set compose `version:`.

### 7.1 `compose.yaml` (implement this shape)

```yaml
name: toponym

services:
  toponym:
    build:
      context: .
      dockerfile: Dockerfile
    image: toponym:local
    init: true
    user: "10001:10001"
    read_only: true
    tmpfs:
      - /tmp:mode=1777
      - /app/knowledge:uid=10001,gid=10001,mode=0755
    ports:
      - "127.0.0.1:8099:8099"
    environment:
      TOPONYM_BIND: "0.0.0.0"
      TOPONYM_PORT: "8099"
      TOPONYM_DB: "/app/knowledge/registry.db"
      TOPONYM_ALLOW_NON_LOOPBACK: "1"
    cap_drop:
      - ALL
    security_opt:
      - "no-new-privileges:true"
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=2).read()",
        ]
      interval: 10s
      timeout: 3s
      start_period: 40s
      retries: 5
    restart: unless-stopped
```

Forbidden in this file: services `searxng`, `ollama`, `local-deep-research`, `pxpipe`, `gateway`, `dashboard`; any `ports` other than `127.0.0.1:8099:8099`; `network_mode: host`; `privileged: true`; extra `cap_add`.

No named volume for canon (canon is in the image). FTS lives on tmpfs and is rebuilt each start.

### 7.2 `Dockerfile`

```
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TOPONYM_BIND=0.0.0.0 \
    TOPONYM_PORT=8099 \
    TOPONYM_DB=/app/knowledge/registry.db \
    TOPONYM_ALLOW_NON_LOOPBACK=1

WORKDIR /app

# Copy only what pip + validate + index need. Never the template.
COPY pyproject.toml README.md LICENSE datapackage.json ./
COPY scripts ./scripts
COPY schema ./schema
COPY data ./data
COPY ontology ./ontology

RUN pip install --no-cache-dir . \
    && useradd --system --uid 10001 --gid nogroup --home /app --no-create-home toponym \
    && mkdir -p /app/knowledge \
    && chown -R 10001:nogroup /app/knowledge \
    && chmod +x /app/scripts/entrypoint.sh

USER 10001:nogroup

EXPOSE 8099

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
```

`useradd` group: if `nogroup` gid is not 10001, compose `user: "10001:10001"` will fail on `/app/knowledge`. **Prefer creating group 10001** so compose and image match:

```
RUN groupadd --gid 10001 toponym \
 && useradd --system --uid 10001 --gid 10001 --home /app --no-create-home toponym
```

Then `USER 10001:10001` and compose `user: "10001:10001"`.

Install **`.` not `.[dev]`** (no pytest/ruff in the runtime image). Do not install `uv` in the image. If `pip install .` tries to compile (should not; frictionless/pyyaml/requests have wheels), pin wheels only — do not leave `build-essential` in the final image. Multi-stage is allowed in P11 only if a compiler is proven necessary; default is single stage.

`EXPOSE 8099` is documentation; it does not publish on the host.

### 7.3 `scripts/entrypoint.sh`

```sh
#!/bin/sh
set -eu
cd /app
python scripts/validate.py
python scripts/index.py --out "${TOPONYM_DB:-/app/knowledge/registry.db}"
exec python scripts/serve.py
```

- `validate.py` non-zero → container exits, never healthy.
- `index.py` non-zero → same.
- `exec` so PID 1 is the server (with compose `init: true` as a sidecar reaper).
- Do not run `check.py` / `sync.py`.
- LF, executable bit in git (`chmod +x`).

### 7.4 `.dockerignore` (minimum)

```
.git
.github
.venv
.agent
.pytest_cache
**/__pycache__
**/*.pyc
agentic_loop_template
agentic_loop_template/
knowledge
tests
prompts
.env
.env.*
*.db
```

Must exclude `agentic_loop_template` so a local symlink cannot vendor the harness into the image. Must exclude `.venv` (host 3.14). Do **not** ignore `data/` or `schema/`.

A file-contract test (P11) greps `.dockerignore` for `agentic_loop_template` and `.venv`.

### 7.5 Image content policy

- No file from `data/` in the build context may exceed 10 MB (already true; `tests/test_no_vendor.py` stays the gate).
- Do not `curl` GeoNames/GAR during build.
- Do not `COPY` `tests/` (runtime image is not a test runner).

---

## 8. Tests

Two layers. Default `pytest -q` on CI (Python 3.12, **no Docker required**) must stay green.

### 8.1 Handler-level (always run) — `tests/test_serve.py`

Pattern: reuse `tests/test_index.py` `_build(tmp_path)` (or call `rebuild_index(ROOT, tmp_path / "registry.db")`), then `handle(Request(...), db_path)` — **no `HTTPServer`, no `time.sleep`, no port bind**.

Required cases:

1. `GET /v1/search?q=Волга` → 200, `wd:Q626` in `ids`, hit `table_name == "hydronyms-major"`.
2. `GET /v1/search?q=МВД` → 200, `foiv:mvd` in `ids`.
3. Missing `q` → 400 `missing_query`.
4. Empty / whitespace `q` → 400 `missing_query`.
5. `q` longer than 200 → 400 `query_too_long`.
6. `q` containing `"` and FTS operators (`AND`, `*`) → 200 or 400, **never 500**.
7. `limit=0` / `limit=101` / `limit=abc` → 400 `invalid_limit`.
8. `GET /v1/records?id=wd:Q626` → 200, `hit.id == "wd:Q626"`.
9. Unknown id → 404 `not_found`.
10. `GET /nope` → 404.
11. `POST /v1/search` → 405.
12. `GET /healthz` with missing db → 503.
13. `GET /healthz` after rebuild → 200, `ok true`, `records > 0`.
14. `parse_args([])` → bind `127.0.0.1`, port `8099`.
15. `main(["--bind", "0.0.0.0"])` without allow flag → exit 2, does not listen.
16. JSON `Content-Type` includes `charset=utf-8`; body is valid UTF-8 (`Волга` not `\u0412…` because `ensure_ascii=False`).

Do **not** start a background thread “for realism” in this file.

Optional tiny unit in `tests/test_index.py`: `fts_search(..., limit=1)` returns dicts with `id`. Do not break `fts_match`.

### 8.2 Compose file-contract (always run) — `tests/test_compose.py`

No daemon. Read YAML/text:

1. `compose.yaml` exists; top-level `name == "toponym"`.
2. Exactly one service, key `toponym`.
3. `ports == ["127.0.0.1:8099:8099"]` (string match; reject `8099:8099` and `0.0.0.0:8099:8099`).
4. `cap_drop` contains `ALL`; `security_opt` contains `no-new-privileges:true`; `read_only` is true; `user` is `10001:10001`.
5. Service names do not include `searxng`, `ollama`, `local-deep-research`, `pxpipe`, `gateway`, `dashboard`.
6. File text does not mention `:8100`, `:8110`, `:8112`, `:8080` as published ports (comment mentioning “do not steal 8110” is allowed; a pytest regex on `ports:` blocks is safer).
7. `Dockerfile` `FROM python:3.12-slim-bookworm` (or `python:3.12-slim`).
8. `.dockerignore` contains `agentic_loop_template` and `.venv`.
9. `scripts/entrypoint.sh` calls `validate.py` then `index.py` then `serve.py`.

### 8.3 Compose smoke (skip if no Docker) — `tests/test_compose_smoke.py`

```python
@pytest.mark.skipif(not docker_ok(), reason="docker unavailable")
```

`docker_ok()`: `shutil.which("docker")` and `docker compose version` exit 0 and `docker info` exit 0. **Default CI job does not require this** (GitHub runners have Docker, but a skip keeps laptop/CI without the daemon green). Do not add a second GHA job in loop 2.

When not skipped:

1. `docker compose -f compose.yaml up --build -d --wait` from repo root (timeout ~180s).
2. `urllib.request.urlopen("http://127.0.0.1:8099/healthz")` → 200 `ok`.
3. search `q=Волга` → `wd:Q626`; `q=МВД` → `foiv:mvd`.
4. `finally: docker compose -f compose.yaml down -v`.

Do not leave a running daemon if the test fails (`try/finally`). Do not publish to a random port — 8099 is the contract; if 8099 is busy, skip (`pytest.skip("8099 in use")`) rather than fight Agentix.

Mark with `@pytest.mark.slow` if you add a pytest marker; do not put `--runslow` in `addopts` (default `pytest -q` should skip only via `skipif`).

### 8.4 CI

`.github/workflows/ci.yml` stays: Python 3.12, `ruff check scripts tests`, `pytest -q`, `python scripts/validate.py`. No docker-build step in loop 2. Ruff must include `scripts/serve.py` (already `src = ["scripts", "tests"]`).

---

## 9. INVEST slices (P10+)

Add this table to `CYCLE_PLAN.md` in P10. Sequential. No parallel (unlike P2∥P6). Do not split P10 into sub-cycles.

| ID | Slice | Branch | Acceptance | Status |
|---|---|---|---|---|
| P10-SERVE | stdlib loopback JSON over FTS | `feature/P10-serve` | `handle()` search `Волга`/`МВД`; bind default `127.0.0.1`; non-loopback refused; `fts_match` tests still green | COMPLETE |
| P11-BOX | Dockerfile + `compose.yaml` + entrypoint | `feature/P11-compose` | file-contract tests in §8.2 green; image is 3.12; `cap_drop: ALL`; entrypoint validate→index→serve; `.dockerignore` excludes template | COMPLETE |
| P12-DOCS | README docker 5-min, ontology `DEC-SERVE-001`, CHANGELOG | `feature/P12-docs` | README copy-paste `docker compose up --build`; reserved-port table; v1 host path intact | COMPLETE |
| P13-DONE | Reviewer gate | `feature/P13-release` optional | pytest + ruff + validate; no file >10 MB; no empty commit; **no new git tag unless operator asks** | COMPLETE |
| P14-REL | CalVer tag `2026.09.11` | `feature/P14-release` | CHANGELOG dated section; pyproject/CITATION; annotated tag + GitHub Release | COMPLETE |
| P15-DOCS | docs match tag `2026.09.11` | `feature/P15-docs` | README, CYCLE_PLAN, this snapshot | COMPLETE |

### P10-SERVE

**Depends on:** v1 on `main` (index.py, seeds).

**Creates/changes:**

- `scripts/serve.py` (new)
- `scripts/index.py` — add `fts_search` only; do not change `SCHEMA_SQL` / `fts_match` semantics
- `tests/test_serve.py` (new)
- `CYCLE_PLAN.md` — Loop 2 table with P10 in progress / others pending

**Does not:** Dockerfile, README rewrite, ontology, pyproject deps, CalVer bump.

**Acceptance:** `pytest tests/test_serve.py tests/test_index.py` green without Docker.

### P11-BOX

**Depends on:** P10 merged.

**Creates/changes:**

- `Dockerfile`, `compose.yaml`, `.dockerignore`, `scripts/entrypoint.sh`
- `tests/test_compose.py`
- `tests/test_compose_smoke.py` (skipif)

**Does not:** mix Agentix services; publish non-loopback; `pip install .[dev]` in image; `COPY` the template.

**Acceptance:** file-contract tests always run; smoke skipif; `ruff` on any new Python (entrypoint is shell).

### P12-DOCS

**Depends on:** P11 merged.

**Creates/changes:**

- `README.md` — second 5-min path (Docker). Keep the venv path first. Document `127.0.0.1:8099` and reserved Agentix ports.
- `CHANGELOG.md` `[Unreleased]` — Added: loopback `serve.py`, compose box.
- `ontology/ontology.json` + `tests/test_ontology.py` `REQUIRED_IDS`:
  - `DEC-SERVE-001` type Decision, status accepted, date 2026-09-11, summary: stdlib loopback HTTP + one-service compose; not Datasette/FastAPI/CKAN; not Agentix stack; not a public API
  - `ART-SERVE` Artifact `scripts/serve.py`
  - `ART-COMPOSE` Artifact `compose.yaml`
  - `RSK-PUBLIC-BIND` Risk: non-loopback bind
  - `RSK-PORT-COLLISION` Risk: stealing `:8080/:8100/:8110/:8112`
- `CYCLE_PLAN.md` — mark P10–P12 COMPLETE
- Optional living snapshot `docs/design/2026-09-11-loop2-compose-box.md` that **points at this brief** and freezes the JSON/compose contracts (do not leave SSOT only under `.agent/` after P12). Copy the normative tables from §§5–7, not a prose essay.
- `docs/design/2026-09-09-v1-local-registries.md` — one sentence: loop 2 serve/compose is listed in `CYCLE_PLAN.md` (so the v1 line “do not start serve.py unless CYCLE_PLAN lists them” remains true). Do not restyle the v1 document.

**Does not:** bump `pyproject.toml` version off `2026.09.09` unless the operator wants CalVer `2026.09.11`. Default: keep `2026.09.09` on the package, document loop 2 as Unreleased.

### P13-DONE

Reviewer checklist only. If P12 already has the docs, **do not empty-commit**. Tag/release is operator-initiated (unlike v1 P9). Merge policy unchanged.

---

## 10. Docs / ontology / CHANGELOG (content freeze for P12)

README Docker block (English or Russian matching the current README voice — README is Russian, keep Russian):

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
docker compose up --build
# http://127.0.0.1:8099/healthz
# http://127.0.0.1:8099/v1/search?q=Волга
```

Note: does not start SearXNG, Ollama, or pxpipe. Host Agentix ports 8080/8100/8110/8112 stay free.

Scripts list in README: add `python scripts/serve.py`.

`TASK_SPECIFICATION.md`: do **not** rewrite v1 “serve.py out of scope” as if v1 changed. Add a short **Loop 2** subsection after Success Criteria, or leave spec at v1 and let `CYCLE_PLAN.md` + `docs/design/2026-09-11-loop2-compose-box.md` carry loop 2. Prefer **not** retconning the v1 spec; CYCLE_PLAN is the executable list (v1 design key decision 2).

---

## 11. Security

| Threat | Mitigation |
|---|---|
| Public bind / LAN scrape | Default `127.0.0.1`; refuse `0.0.0.0` without explicit flag; compose publishes `127.0.0.1:8099:8099` only |
| Port collision with pxpipe/gateway | Port **8099**; tests forbid 8080/8100/8110/8112 |
| FTS MATCH injection | Phrase-quote user `q`; length cap 200; catch OperationalError |
| Write API | GET only |
| Privilege | `USER 10001`; `cap_drop: ALL`; `no-new-privileges`; `read_only` rootfs; tmpfs for db |
| Template/harness leak into image | `.dockerignore` + test |
| Dump vendor via Docker | No fetch in Dockerfile; `test_no_vendor.py` still applies to `data/` |
| SSRF | Serve does not fetch URLs |
| CORS drive-by | No CORS headers |

Threat model is still a **local appliance**, now with an inbound loopback port. That is a deliberate expansion of v1 “no inbound ports” (v1 design Security). `DEC-SERVE-001` records it.

---

## 12. Out of scope (loop 2)

- Public/LAN API, TLS, auth tokens, HTML UI, OpenAPI, CORS.
- Datasette, FastAPI, DuckDB server, CKAN.
- Agentix SearXNG / LDR / Ollama / dashboard / gateway in this compose.
- `check.py` / `sync.py` inside the container.
- Incremental FTS, write-back, GeoJSON, tiles, SPARQL.
- Streets / municipalities / GAR / `RU.zip` (still v1 non-goals).
- Host Python 3.14 support patches; the box **is** the 3.12 pin.
- CalVer tag `2026.09.11` (operator).
- CI docker-build job.
- Bind-mount of the git tree for live CSV (rebuild image after pull).
- Copying `agentic_loop_template/deploy/compose.yaml`.

---

## 13. Implementation notes for the Coder

- Copy CLI bootstrap and argparse style from `scripts/index.py` / `scripts/check.py`.
- JSON stdout style from `check.py` (`ensure_ascii=False`). Serve HTTP bodies may use compact separators; tests should `json.loads`.
- Rebuild index in tests against **repo `ROOT`**, same as `tests/test_index.py` (real Волга/МВД rows).
- `knowledge/` may not exist on a fresh clone; `rebuild_index` already `mkdir` via `_unlink_db`. Serve must not create the db (503 instead); entrypoint runs `index.py`.
- Keep `pyproject.toml` dependencies unchanged.
- `scripts/entrypoint.sh` uses `sh` (dash on slim), not bash arrays.
- Windows is not a loop 2 target; compose file is the install box.
- If 8099 is taken on a dev host, do not silently pick another port in compose; document `docker compose down` / stop the leftover box.

### Suggested commit messages (Russian, human)

- P10: `feat(serve): loopback JSON-поиск по FTS на 127.0.0.1:8099`
- P11: `feat(compose): установочный ящик Python 3.12, validate → index → serve`
- P12: `docs: Docker Compose за 5 минут и решение DEC-SERVE-001`

---

## 14. Definition of Done (loop 2)

- [x] `python scripts/serve.py` on the host binds `127.0.0.1:8099` and answers Волга/МВД
- [x] `docker compose up --build` on a clone does the same without host CPython 3.12
- [x] Handler tests green without a daemon; compose file-contract green without Docker; smoke skipif
- [x] No new runtime dependency; no template tree in the image
- [x] Ports 8080/8100/8110/8112 unpublished
- [x] Ontology has `DEC-SERVE-001`; CHANGELOG `[2026.09.11]` dated
- [x] v1 CSV canon, detectors, and `fts_match` tests untouched in spirit (no schema rewrite)

---

## 15. Critical files (for the Coder)

| Path | Role |
|---|---|
| `scripts/index.py` | Add `fts_search`; keep `rebuild_index` / `fts_match` |
| `scripts/serve.py` | New: `handle` + stdlib HTTP |
| `tests/test_index.py` | Pattern for rebuild + Волга/МВД |
| `compose.yaml` + `Dockerfile` | Install box contract |
| `ontology/ontology.json` | `DEC-SERVE-001` in P12 |
| `CYCLE_PLAN.md` | Executable P10–P13 table |
