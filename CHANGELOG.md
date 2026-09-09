# Changelog

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: Calendar Versioning `YYYY.MM.DD`.

## [Unreleased]

Сиды канона, схемы, скрипты и онтология **есть в дереве** (P0–P7). Календарная секция `[2026.09.09]` появится при теге релиза.

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

### Changed
- Каталог источников: обязательные `vendor` и `detector.kind`.
- В `types.csv` у `oikonym` восстановлены `example_ru=Москва` и класс GeoNames `P`.
- GeoNames id: Москва `524901`, Волга `472776`.
- Склонения: `review=gold` / `needs_review` (не boolean).
