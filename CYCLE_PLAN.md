# CYCLE_PLAN.md — toponym (v1 `2026.09.09`, loop 2 `2026.09.11`)

Исполняемый план циклов. Детали интерфейсов: `docs/design/2026-09-09-v1-local-registries.md`.
Спека: `TASK_SPECIFICATION.md`. ADR: `LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md`.

**Правило оператора:** в конце каждого цикла — merge в `main` и `git push origin main`.
Коммиты на русском, от лица разработчика. Пустой коммит запрещён.

Параллель: только P2 ∥ P6 после P1. Синхроточка: после P5.

| ID | Слайс | Ветка | Acceptance | Status |
|---|---|---|---|---|
| P0-BOOT | схемы, pyproject, catalog detectors, Agentix-файлы | `feature/P0-boot` | jsonschema catalog; pytest `tests/test_schema.py`; datapackage schema paths существуют | COMPLETE |
| P1-SEED | сиды ФО / 89 субъектов / города / гидро / оро / ФОИВ / склонения | `feature/P1-seed` | все resources datapackage ≥1 строка; types.oikonym починен | COMPLETE |
| P2-MAP | mappings YAML | `feature/P2-map` | yaml валиден `mapping.schema.json` | COMPLETE |
| P3-CHECK | `scripts/check.py` | `feature/P3-check` | exit 0/10/2; JSON; pytest без сети | COMPLETE |
| P4-SYNC | `scripts/sync.py` upsert/deprecate | `feature/P4-sync` | фикстура 2→3; delete не стирает | COMPLETE |
| P5-VAL | `scripts/validate.py` + CI | `feature/P5-val` | ломаный CSV падает; дерево = 0 | COMPLETE |
| P6-INDEX | `scripts/index.py` FTS5 | `feature/P6-index` | MATCH «Волга» и «МВД» | COMPLETE |
| P7-ONT | `ontology/ontology.json` | `feature/P7-ont` | DEC-REG-001 + Source на каждый catalog id | COMPLETE |
| P8-DOCS | README 5 мин, CHANGELOG, daily | `feature/P8-docs` | команды README копируются; daily → check.py | COMPLETE |
| P9-DONE | reviewer + tag `2026.09.09` | `feature/P9-release` | pytest+ruff+validate; нет файлов >10 МБ; GitHub Release | COMPLETE |

## Post-v1

| ID | Слайс | Ветка | Acceptance | Status |
|---|---|---|---|---|
| v1.1-HTTP-DATED | `http_dated`: `changed` только RU-строки; `also` не флипает | `feature/v1.1-http-dated` | non-RU + dump Last-Modified → exit 0; cursor остаётся датой mods | COMPLETE |
| v1.1-DOCS-DRIFT | дизайн v1 = выпущенный контур; geonames Москва/Волга | `feature/v1.1-docs-drift` | design не говорит «P6 next»; Q649=524901, Q626=472776 | COMPLETE |

## Loop 2 (compose box, DEC-SERVE-001)

Последовательность. Не параллелить. Канон v1 не переписывать.

| ID | Слайс | Ветка | Acceptance | Status |
|---|---|---|---|---|
| P10-SERVE | stdlib loopback JSON над FTS | `feature/P10-serve` | `handle()` поиск «Волга»/«МВД»; bind `127.0.0.1:8099`; не-loopback отказ; `fts_match` зелёный | COMPLETE |
| P11-BOX | Dockerfile + compose.yaml + entrypoint | `feature/P11-compose` | file-contract: 3.12, `cap_drop: ALL`, `127.0.0.1:8099`; `.dockerignore` без шаблона | COMPLETE |
| P12-DOCS | README docker, ontology DEC-SERVE-001, CHANGELOG | `feature/P12-docs` | `docker compose up --build` в README; v1 host-путь цел | COMPLETE |
| P13-DONE | reviewer gate | `feature/P13-release` | pytest+ruff+validate; без файлов >10 МБ; тег только по запросу оператора | COMPLETE |
| P14-REL | tag `2026.09.11` + GitHub Release | `feature/P14-release` | CHANGELOG dated; pyproject/CITATION; annotated tag | COMPLETE |
| P15-DOCS | docs match `2026.09.11` | `feature/P15-docs` | README, CYCLE_PLAN, design snapshot | COMPLETE |
| P16-PRES | продуктовая колода | `feature/P16-presentation` | `docs/presentation/`: CSV, check/sync/validate/index, :8099, compose | COMPLETE |
| P17-README | world-class README + shields.io | `feature/P17-readme` | бейджи MIT/CalVer/CI/python/compose; `docker compose up --build`; `127.0.0.1:8099` healthz/search | COMPLETE |
| P18-USAGE | user guide search + declensions | `feature/P18-usage` | `docs/USAGE.md`: healthz, GET search/records, CSV join по id, офлайн; README ссылается | COMPLETE |
| P19-DEPLOY | min first-run / update | `feature/P19-deploy` | README: первый запуск `docker compose up --build`; обновление `git pull && docker compose up --build`; хост Agent-Init + serve.py | COMPLETE |
| P20-CHANGELOG | Unreleased USAGE + min-update | `feature/P20-changelog` | CHANGELOG Unreleased датирует USAGE и `git pull && docker compose up --build`; тег `2026.09.11` не двигается | COMPLETE |

## Next release (после `2026.09.11`)

Non-goals v1 → явные строки. Исполнять **по одному** PENDING. Канон v1 не переписывать.
Keep-out закрывается онтологией `DEC-*` в `ontology/ontology.json` (формат только Outpost).
Основной build-слайс — **K** (малые сиды МО / годонимов / микротопонимов). Дампы >10 МБ, полный ГАР/`RU.zip` — вне git.

| ID | Слайс | Ветка | Acceptance | Status |
|---|---|---|---|---|
| A | `RU.zip` / ГАР вне git: SOURCE.md + fetch в tmp | `feature/nr-a-dump` | указатели `data/raw/*/SOURCE.md`; опциональный fetch пишет вне репо; size gate; дамп не коммитится | COMPLETE |
| B | Немаппленные `gn:{id}` не вставлять в curated | `feature/nr-b-geonames` | дизайн + DEC: GeoNames sync только match существующих строк; без `gn:{id}` insert | COMPLETE |
| C | pymorphy/Natasha не золото | `feature/nr-c-declensions` | автосклонения только `review=needs_review` или `data/declensions/queue.csv`; gold не трогать | COMPLETE |
| D | Уникальность склонений `(id, lemma)` | `feature/nr-d-decl-key` | DEC: не форсировать unique `id`; золото не переписывать | COMPLETE |
| E | Таксономия верхнего уровня | `feature/nr-e-taxonomy` | DEC: `toponym` / `oikonym` / `hydronym` без переименования | COMPLETE |
| F | Публичный HTTP вне scope | `feature/nr-f-loopback` | loopback `127.0.0.1:8099`; host publish не `0.0.0.0`; публичный Internet API нет | COMPLETE |
| G | Один формат онтологии | `feature/nr-g-ontology` | только Outpost `ontology/ontology.json`; DEC-* на keep-out A–J, L | PENDING |
| H | Agentix — symlink SSOT | `feature/nr-h-agentix` | DEC: дерево шаблона не копировать; sibling `../agentic_loop_template` | PENDING |
| I | hflabs CC-BY-SA не в curated | `feature/nr-i-hflabs` | DEC + `data/raw/`: ShareAlike только raw; curated без копий таблиц | PENDING |
| J | Население / полигоны / GeoJSON / PostGIS | `feature/nr-j-geo` | вне канона; опциональный указатель в docs; CSV-канон не расширять геометрией | PENDING |
| K | Сиды муниципалитетов, годонимов, микротопонимов | `feature/nr-k-seeds` | новые curated CSV + resource datapackage + schema; ≥1 строка каждый; типы уже есть; без дампа ГАР | PENDING |
| L | Не дробить P1 на P1a–e | — | P1 COMPLETE; подциклы не открывать | COMPLETE |

## Definition of Done v1

- Все 11 resources из `datapackage.json` на диске.
- `python scripts/check.py --json` без секретов.
- `python scripts/validate.py` = 0.
- Daily: дельта или `data/sources/runs/YYYY-MM-DD.json`, без пустого commit.
- Онтология содержит DEC-REG-001.
- Тип верхнего уровня `toponym` цел.

## После каждого цикла

```bash
pytest -q
git checkout main
git merge --no-ff feature/P{n}-*
git push origin main
```

Daily-промпт: [`agents/DAILY_UPDATE.md`](agents/DAILY_UPDATE.md).
