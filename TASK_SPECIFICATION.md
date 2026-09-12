# TASK_SPECIFICATION.md — toponym

**Project:** toponym (`unhexx/toponym`)
**Version Target:** v1 `2026.09.09`; loop 2 `2026.09.11`; текущий тег `2026.09.16`.
**Primary Goal:** Собрать в одном git-репозитории качественный локальный реестр российских топонимов и ведомств: CSV-канон, источники с лицензиями и детекторами, скрипты обновления, derived SQLite FTS, онтология.

ADR и исследование: [`LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md`](LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md) (DEC-REG-001).

## Business Objectives

- Любое приложение читает канон как UTF-8 CSV без SDK.
- `datapackage.json` + Table Schema дают машинную валидацию.
- Есть ли обновление источника — видно по `check.py`; дельта применяется upsert-ом.
- Ежедневный прогон либо патчит канон, либо пишет runs-журнал, без пустого коммита.

## Scope

**In scope:**

- Сиды: ФО, субъекты РФ, крупные города, гидронимы/оронимы, ФОИВ и прочие органы, золотые склонения.
- Mappings: GeoNames, ГКГН-указатель, Указ №326, hflabs.
- Скрипты: `check.py`, `sync.py`, `validate.py`, `index.py`.
- Онтология Outpost `ontology/ontology.json` (Source / Registry / Mapping / Check / Decision).
- Документация quick start + CHANGELOG CalVer.

**Out of scope:**

- Полный импорт RU.zip / ГАР.
- Автосклонения pymorphy как золото.
- Переписывание таксономии верхнего уровня.
- Публичный HTTP API (`serve.py` — вне v1).
- Второй формат онтологии помимо Outpost `ontology.json`.

## Canonical rules (from CONTRIBUTING.md)

- Патч CSV по stable id; delete запрещён (`status=deprecated` + `replaced_by`).
- Дампы >10 МБ и полный ГАР/ФИАС не вендорятся.
- CC BY-SA и ODbL только в `data/raw/<source>/`.
- `ё` в `name_yo`; в `name_ru` нормализация ё→е.
- UTF-8, LF, CSV delimiter = запятая.

## Success Criteria (Definition of Done v1)

- Все resources из текущего `datapackage.json` существуют и содержат ≥1 строку.
- `python scripts/check.py --json` работает без секретов.
- `python scripts/validate.py` = 0.
- Daily либо применяет дельту, либо пишет `data/sources/runs/YYYY-MM-DD.json` и не делает пустой commit.
- Онтология содержит DEC-REG-001 и список Source.
- Верхний уровень типов цел (`toponym`, не «Торопум»).
- Тесты зелёные, нет вендора >10 МБ.

## Loop 2 (after v1)

Executable list: `CYCLE_PLAN.md` (P10–P13). Design SSOT: `docs/design/2026-09-11-loop2-compose-box.md` (DEC-SERVE-001). v1 non-goals above stay true for the tagged release; loop 2 adds loopback `scripts/serve.py` and a one-service Compose box on `127.0.0.1:8099`. Do not retcon v1.

## After loop 2 (A–L)

Keep-out A–L COMPLETE на `main` (`CYCLE_PLAN.md`). Живой backlog: GitHub #13. Не retcon v1 non-goals. Теги `2026.09.11`, `2026.09.12`, `2026.09.13`, `2026.09.14` и `2026.09.15` не двигать; текущий — `2026.09.16`.

## Cycles (INVEST)

| ID | Slice | Acceptance |
|---|---|---|
| P0-BOOT | PLAN, SPEC, catalog.schema.json | файлы на ветке, schema validate |
| P1-SEED | сиды ФО, субъекты, ФОИВ, крупные гидро/оро, types | datapackage resources, ≥1 строка |
| P2-MAP | mappings GeoNames, ГКГН, 326, hflabs | yaml валиден mapping.schema |
| P3-CHECK | `scripts/check.py` | код 0 на no-op; JSON-отчёт |
| P4-SYNC | `scripts/sync.py` upsert + deprecate | фикстура: 2→3 строки, delete не стирает |
| P5-VAL | `scripts/validate.py` + frictionless | ломаный CSV падает |
| P6-INDEX | `scripts/index.py` SQLite FTS | поиск «Волга» / «МВД» |
| P7-ONT | ontology.json | валидный JSON, DEC-REG-001 |
| P8-DOCS | README, CHANGELOG, DAILY_UPDATE → check.py | человек поднимает за 5 мин |
| P9-DONE | релиз 2026.09.09 | тесты зелёные, tag |

Параллелить можно только P2 и P6 после P1; остальное последовательно. Синхроточка: после P5.

Оператор явно требует: в конце каждого цикла merge в `main` и push.


