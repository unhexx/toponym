# Compose-ящик и loopback-поиск (DEC-SERVE-001)

Актуальная витрина: [`README.md`](../../README.md). Оглавление: [`docs/README.md`](../README.md).

Снимок выпущенного контура. Тег `2026.09.11`. План: `CYCLE_PLAN.md`. Канон v1 (`docs/design/2026-09-09-v1-local-registries.md`) не переписывать.

## Цель

Один сервис Docker Compose:

1. Python 3.12.
2. Зависимости из `pyproject.toml` (без новых runtime-библиотек).
3. Старт: **validate → index → serve**.
4. JSON-поиск по SQLite FTS5 (`knowledge/registry.db`) только на loopback.
5. Не публичный API и не портал данных.

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
docker compose up --build
curl -sG 'http://127.0.0.1:8099/v1/search' --data-urlencode 'q=Волга'
```

Хост без Docker: `.venv` + `pip install -e ".[dev]"` + `python scripts/serve.py`.

## Контракт

- Канон — UTF-8 CSV в git. SQLite FTS — derived, gitignored.
- Дампы >10 МБ и полный ГАР/`RU.zip` не в git и не в образ.
- Bind на хосте: `127.0.0.1:8099`. В контейнере слушает `0.0.0.0` только потому, что publish на loopback.
- Образ: `python:3.12-slim`, user `10001`, `cap_drop: ALL`, read-only.
- HTTP: GET `/healthz`, `/v1/search`, `/v1/records`. Не-GET — 405.
- Не публиковать 8080 / 8100 / 8110 / 8112.

Файлы: `scripts/serve.py`, `Dockerfile`, `compose.yaml`, `scripts/entrypoint.sh`, `.dockerignore`.
