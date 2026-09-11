# Changelog

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: Calendar Versioning `YYYY.MM.DD`.

## [Unreleased]

### Fixed
- Daily: таймаут `http_head` у указателей (Росреестр/ФИАС) больше не даёт `check.py` код 2 и не блокирует GeoNames. Журнал `data/sources/runs/` пишется и при коде 2; `workflow_dispatch` — `--ref main`, не `main~`.

### Changed
- Ручная приёмка высокочастотных склонений в `gold`: 15 городов-миллионников плюс Тольятти/Улан-Удэ (нескл.) и Ярославль, Саратов, Иркутск, Владивосток, Томск, Тюмень; творительный Воронежа — **Воронежем**. Аббревиатуры КС РФ, ВС РФ, АП, Совбез, Генпрокуратура, СК России, Банк России, ЦИК России, Счётная палата. Норма в `source` (`Розенталь; Грамота.ру`). Остаток городов/полных имён ФОИВ — `needs_review`. Фикстуры DECLENSIONS.md не переписывались.

### Added
- Образ `ghcr.io/unhexx/toponym:2026.09.12` (и `:CalVer`) публикуется CI на push в `main`. `compose.yaml` пинит этот тег, `build` остаётся опциональным. Обновление без сборки: `docker compose pull && docker compose up`.
- CI: отдельный job `compose` (`docker compose up --build --wait`, curl `/healthz` и поиск Волга/МВД, timeout 20 мин). Unit-job `pytest -m "not compose"` без Docker.
- Указатель [`data/mappings/wikidata.yaml`](data/mappings/wikidata.yaml): Q-id → `wd`, label ru/en, P625 → `lat`/`lon` (точки, DEC-GEO-001). SPARQL-дамп не вендорится; `delete_policy=pointer`.
- Указатель [`data/mappings/hflabs-city.yaml`](data/mappings/hflabs-city.yaml): join по FIAS GUID; `city`/`name` в curated не копируются (DEC-HFLABS-001). Таблица hflabs в git не кладётся.
- Сиды МО / годонимов / микротопонимов расширены из Wikidata (CC0): десятки городских округов, улиц и урочищ/пещер. Стабильные `wd:` id, `parent_id` на субъект или город. Склонения новых строк — `review=needs_review` (только `nom`), без pymorphy. ГАР/`RU.zip` и hflabs в curated не копировались.
- Сиды дромонимов, сёл и агоронимов (DEC-SEED-002): [`data/curated/dromonyms.csv`](data/curated/dromonyms.csv), [`villages.csv`](data/curated/villages.csv), [`agoronyms.csv`](data/curated/agoronyms.csv) + ресурсы datapackage и склонения `needs_review`. Типы уже были в `types.csv`. Улица ≠ площадь. Без ГАР.
- CLI очереди автосклонений: `python scripts/declensions_queue.py --id … --lemma …` пишет только [`data/declensions/queue.csv`](data/declensions/queue.csv), `review=needs_review`. `--review gold` — отказ (DEC-DECL-001); золотые таблицы не трогает.

## [2026.09.12] - 2026-09-12

Next-release A–L на `main`. Annotated tag `2026.09.12`.

### Added
- Console scripts: `toponym-serve`, `toponym-index`, `toponym-validate`, `toponym-check` после `pip install .`. `python scripts/*.py` по-прежнему работает.
- FTS: `lemma`/`yo`/заполненные падежи из `data/declensions/*.csv` — поисковые алиасы (канон CSV не дублируется в `records`). USAGE: раздел про сиды МО/улиц/микротопонимов (по 2 строки, не ГАР).
- FTS `records` и HTTP-карточка: `lat`/`lon`/`fias`/`oktmo` (координаты не токенизируются в FTS5).
- `GET /v1/declensions?id=…` — падежи из `data/declensions/*.csv` (не FTS). Несколько лемм на id — массив hits. USAGE: curl вместо grep.
- Склонения гидронимов, оронимов, МО, годонимов и микротопонимов: отдельные CSV в `data/declensions/` (ресурсы datapackage). Золото «Волга»/`wd:Q626` и «Дон»/`wd:Q1229` (`loc2` Дону) перенесены из `cities-major.csv`. Остальные строки — `review=needs_review`, без pymorphy.
- Малые сиды [`data/curated/municipalities.csv`](data/curated/municipalities.csv), [`hodonyms.csv`](data/curated/hodonyms.csv), [`microtoponyms.csv`](data/curated/microtoponyms.csv) (DEC-SEED-001): типы уже в `types.csv`; схема `places.schema.json`; ≥1 строка; без дампа ГАР.
- Очередь автосклонений [`data/declensions/queue.csv`](data/declensions/queue.csv) (не ресурс datapackage).
- `scripts/fetch_dump.py` — опциональная выгрузка GeoNames `RU.zip` / ГАР / ГКГН **вне** дерева git (`--dest` внутри репозитория — ошибка; указатели ГАР/ГКГН требуют `--url`). Size gate `data/` и tracked-файлов не снимается.
- Руководство [`docs/USAGE.md`](docs/USAGE.md) — `GET /healthz`, `/v1/search`, `/v1/records` (только loopback); склонения через CSV join по `id` (HTTP падежей не отдаёт); офлайн CSV/SQLite; сеть только для `check.py` / `sync.py`.
- Обновление Compose-ящика одной строкой: `git pull && docker compose up --build`.

### Changed
- `name_yo`: инвентаризация канона по Wikidata ru-label / P1448 / P1705 (CC0). Заполнены только имена, где ё в самом каноне: Орёл, Щёлково, Артём, Королёв, Киселёвск, Чёрное море; плюс норма ФОИВ (молодёжи, Счётная палата). Алиасы не копировались. `validate.py` сверяет `name_ru` = ё→е от `name_yo`.
- Колонка `geonames` дозаполнена по Wikidata P1566 на существующих строках (города/гидро/оро/субъекты); неоднозначные Q-id пропущены. Insert `gn:{id}` по-прежнему запрещён (DEC-GN-001).
- `cities-major.csv`: `lat`/`lon` из Wikidata P625 (CC0) и `oktmo` из P764 для всех 197 строк; `fias` пуст (нет CC0 GUID без дампа ГАР). Полигоны не добавлялись (DEC-GEO-001).
- Геометрия: DEC-GEO-001 — население / полигоны / GeoJSON / PostGIS вне канона; указатель в `docs/SOURCES.md`; `lat`/`lon` остаются точками.
- hflabs: DEC-HFLABS-001 — CC-BY-SA только `data/raw/`; `validate.py` отклоняет `source_id=hflabs-*` в каноне.
- Agentix: DEC-AGENTIX-001 — шаблон только sibling-symlink `../agentic_loop_template`, дерево не в git.
- Онтология: DEC-ONT-001 — только Outpost `ontology/ontology.json`; keep-out A–J, L закрыты DEC-* (дамп, Agentix, hflabs, гео, P1).
- HTTP: DEC-SERVE-002 — публичный Internet API вне scope; host publish только `127.0.0.1:8099`, не `0.0.0.0`.
- Таксономия: DEC-TAX-001 — `toponym` / `oikonym` / `hydronym` не переименовывать; `validate.py` держит корень.
- Склонения: DEC-DECL-002 — уникальность `(id, lemma)`; `id` не unique; золото ФОИВ с двумя леммами не переписывать.
- Склонения: DEC-DECL-001 — pymorphy/Natasha не золото; `validate.py` отклоняет `review=gold` с источником-морфоанализатором; канон не переписывается.
- GeoNames: DEC-GN-001 — sync только match колонки `geonames`; `validate.py` отклоняет `id=gn:…` в местах; немаппленные mods остаются `skipped_unmapped`.
- README: бейджи shields.io (MIT, CalVer `2026.09.12`, CI `ci.yml`, Python 3.12+, Docker Compose), ссылки на `docs/USAGE.md`, CHANGELOG, SOURCES, презентацию и релиз; старт хоста (`.venv`) и `docker compose up --build` с `127.0.0.1:8099/healthz`.
- `scripts/serve.py`: `PACKAGE_VERSION` = `2026.09.12` (`GET /healthz` больше не отдаёт `2026.09.09`).

### Fixed
- `Agent-Init.sh`: без sibling `../agentic_loop_template` — понятное сообщение и fallback `pip install -e ".[dev]"` (не exit 1, дерево шаблона не копируется). README: дефолт «только реестр» — venv + pip, без шаблона. Daily GHA уже ставит пакет без Agent-Init.
- Золото «Волга» (`wd:Q626`): родительный падеж **Волги**, не «Волгы» (Розенталь; `docs/DECLENSIONS.md`). Ручной патч по id, без автосклонения.
- Daily GHA: установка `pip install -e ".[dev]"` без `Agent-Init.sh` (на `ubuntu-latest` нет sibling-шаблона). Журнал `data/sources/runs/YYYY-MM-DD.json` пишется при check 0/10; `checked_at` сдвигается, если устарел. Dead-ветки «нет check.py» убраны.
- SSOT: CYCLE_PLAN DoD — 19 resources; онтология `calver` = `2026.09.12`; ADR помечен историческим снимком v1; SYSTEM_PROMPT/AGENTS — тег `2026.09.12` и backlog #13. `PROJECT_CONTEXT.md` не продукт-SSOT.

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

[Unreleased]: https://github.com/unhexx/toponym/compare/2026.09.12...HEAD
[2026.09.12]: https://github.com/unhexx/toponym/releases/tag/2026.09.12
[2026.09.11]: https://github.com/unhexx/toponym/releases/tag/2026.09.11
[2026.09.09]: https://github.com/unhexx/toponym/releases/tag/2026.09.09
