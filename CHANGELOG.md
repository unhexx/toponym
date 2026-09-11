# Changelog

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: Calendar Versioning `YYYY.MM.DD`.

## [Unreleased]

### Added
- 2026-09-11: руководство [`docs/USAGE.md`](docs/USAGE.md) — `GET /healthz`, `/v1/search`, `/v1/records` (только loopback); склонения через CSV join по `id` (HTTP падежей не отдаёт); офлайн CSV/SQLite; сеть только для `check.py` / `sync.py`.
- 2026-09-11: обновление Compose-ящика одной строкой: `git pull && docker compose up --build`.

### Changed
- README: бейджи shields.io (MIT, CalVer `2026.09.11`, CI `ci.yml`, Python 3.12+, Docker Compose), ссылки на `docs/USAGE.md`, CHANGELOG, SOURCES, презентацию и релиз; старт хоста (`.venv`) и `docker compose up --build` с `127.0.0.1:8099/healthz`.

## [2026.09.11] - 2026-09-11

Loopback JSON-поиск и Docker Compose-ящик на `127.0.0.1:8099` (DEC-SERVE-001). Включает v1.1: `http_dated` только по RU-строкам.

### Added
- Loopback JSON-поиск `scripts/serve.py` на `127.0.0.1:8099` (`/healthz`, `/v1/search`, `/v1/records`).
- One-shot Docker Compose: `docker compose up --build`, Python 3.12, `validate → index → serve`.
- Решение `DEC-SERVE-001`: stdlib HTTP, не Datasette/FastAPI и не стек Agentix.

### Changed
- Дизайн v1 описывает выпущенный контур (P0–P9, geonames Москва `524901` / Волга `472776`), а не «следующий цикл P6».

### Fixed
- `http_dated`: `changed` только по RU-строкам mods/deletes; `also: last_modified_header` не сравнивает Last-Modified дампа с датой-курсором и не подменяет cursor.

## [2026.09.09] - 2026-09-09

Первый релиз локального реестра: канон CSV, детекторы, upsert, FTS, онтология.

### Added
- Каркас репозитория, таксономия типов, каталог источников.
- Контракт v1: Table Schema, JSON Schema каталога и маппингов, `pyproject.toml`.
- Детекторы обновлений в `data/sources/catalog.yaml`.
- Исполняемый ежедневный промпт `agents/DAILY_UPDATE.md` (check → sync → validate → index; журнал `data/sources/runs/`).
- План циклов `CYCLE_PLAN.md` и дизайн v1.
- Сиды канона: 8 федеральных округов, 89 субъектов, крупные города, гидронимы, оронимы, ФОИВ (указ № 326 / № 522) и смежные ведомства.
- Золотые склонения фикстур из `docs/DECLENSIONS.md`, округов, субъектов и аббревиатур ФОИВ.
- Указатели `data/raw/*/SOURCE.md` (hflabs, GeoNames, ФИАС/ГАР, ГКГН, Wikidata) без вендора дампов.
- Маппинги источников: GeoNames, ГКГН, ФИАС-указатель, hflabs/region, указ № 326.
- `scripts/check.py`: детекторы http_head / http_dated / github_commits / page_fingerprint / none.
- `scripts/sync.py`: upsert по id, deprecate без удаления строк, GeoNames только match колонки `geonames`.
- `scripts/validate.py`: frictionless и инварианты канона; CI на Python 3.12.
- `scripts/index.py`: derived SQLite FTS5 (`knowledge/registry.db`); MATCH «Волга», «МВД».
- `ontology/ontology.json`: Outpost v1, DEC-REG-001, Source на каждый id каталога.
- `docs/SOURCES.md`: лицензии и границы вендора.
- Пятиминутный старт в README.

### Changed
- Каталог источников: обязательные `vendor` и `detector.kind`.
- В `types.csv` у `oikonym` восстановлены `example_ru=Москва` и класс GeoNames `P`.
- GeoNames id: Москва `524901`, Волга `472776`.
- Склонения: `review=gold` / `needs_review` (не boolean).

[Unreleased]: https://github.com/unhexx/toponym/compare/2026.09.11...HEAD
[2026.09.11]: https://github.com/unhexx/toponym/releases/tag/2026.09.11
[2026.09.09]: https://github.com/unhexx/toponym/releases/tag/2026.09.09
