# Документация Toponym

Витрина продукта — [README в корне](../README.md). Здесь — указатель файлов.

Реестр ведёт **Evgeniy Chistyakov** aka Unhandled Exception (`unhandled@exception.expert`), [DAO EXCEPTION EXPERT](https://exception.expert).

Поиск слушает только `http://127.0.0.1:8099`. Канон — UTF-8 CSV в git.

## Живые гайды

| Документ | Для кого |
|---|---|
| [USAGE.md](USAGE.md) | уже подняли сервис, ищете имя или падеж |
| [DAILY_UPDATE.md](DAILY_UPDATE.md) | куратор канона, ежедневный прогон |
| [SOURCES.md](SOURCES.md) | лицензии и что нельзя класть в git |
| [DECLENSIONS.md](DECLENSIONS.md) | золотые склонения и очередь |
| [taxonomy.md](taxonomy.md) | типы: ойконим, гидроним, годоним… |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | патч CSV, инварианты, коммиты |

## Машинный канон

| Файл | Роль |
|---|---|
| [../datapackage.json](../datapackage.json) | Frictionless Tabular Data Package (25 resources) |
| [../schema/](../schema/) | JSON Schema таблиц и каталога |
| [../data/sources/catalog.yaml](../data/sources/catalog.yaml) | источники, курсоры, детекторы |
| [../data/curated/types.csv](../data/curated/types.csv) | справочник типов |
| [../ontology/ontology.json](../ontology/ontology.json) | overlay DEC-* |

## История и спецификация

Это снимки решений, не ежедневная инструкция.

| Документ | Роль |
|---|---|
| [design/2026-09-09-v1-local-registries.md](design/2026-09-09-v1-local-registries.md) | выпущенный v1 |
| [design/2026-09-11-loop2-compose-box.md](design/2026-09-11-loop2-compose-box.md) | Compose + loopback |
| [presentation/toponym-2026.09.11.md](presentation/toponym-2026.09.11.md) | продуктовая колода |
| [../TASK_SPECIFICATION.md](../TASK_SPECIFICATION.md) | спецификация |
| [../CYCLE_PLAN.md](../CYCLE_PLAN.md) | план циклов (все слайсы COMPLETE) |
| [../LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md](../LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md) | ADR, исторический снимок |
| [../CHANGELOG.md](../CHANGELOG.md) | CalVer `YYYY.MM.DD` |
| [../CITATION.cff](../CITATION.cff) | цитирование |
| [Релизы](https://github.com/unhexx/toponym/releases) | теги GitHub |

Актуальный тег: [`2026.09.14`](https://github.com/unhexx/toponym/releases/tag/2026.09.14).
