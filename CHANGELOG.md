# Changelog

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: Calendar Versioning `YYYY.MM.DD`.

## [Unreleased]

### Added
- SPARQL-указатели Wikidata для городов, сёл/пгт, площадей, дорог/ЖД, гидронимов и оронимов: [`cities-ru.sparql`](data/raw/wikidata/cities-ru.sparql), [`villages-ru.sparql`](data/raw/wikidata/villages-ru.sparql), [`agoronyms-ru.sparql`](data/raw/wikidata/agoronyms-ru.sparql), [`dromonyms-ru.sparql`](data/raw/wikidata/dromonyms-ru.sparql), [`hydronyms-ru.sparql`](data/raw/wikidata/hydronyms-ru.sparql), [`oronyms-ru.sparql`](data/raw/wikidata/oronyms-ru.sparql). JSON/CSV запроса в git не кладётся.
- CLI `python scripts/seed_cities.py` (P31=Q7930989, P17=Q159; hop P131*; без Крыма/новых субъектов).
- CLI `python scripts/seed_agoronyms.py` (P31=Q174782, P17=Q159; годонимы в skip-set).
- CLI `python scripts/seed_dromonyms.py` (P31=Q34442 + Q728937 ruwiki, P17=Q159; не ПП № 928).
- CLI `python scripts/seed_villages.py` (пгт Q15078955, затем село Q532; шарды субъектов `wall_sec=0`; хутора Q5084 нет).
- CLI `python scripts/seed_hydronyms.py` (озёра Q23397 + реки Q4022 ruwiki, P17=Q159; один SELECT; при too_large/timeout входящие реки отбрасываются, озёра и моря остаются; моря Q165 — FILL_IF_EMPTY, не VALUES; не ГКГН).
- CLI `python scripts/seed_oronyms.py` (гора Q8502, хребет Q46831, вулкан Q8072, остров Q23442, полуостров Q34763, P17=Q159; по одному VALUES-типу; не ГКГН).
- CLI `python scripts/join_foiv.py` — join Wikidata Q-id на существующие ФОИВ (P31 Q4481741/Q4481675/Q14944295, не Q4481793/Q4481792, P17=Q159). Не harvest: `foiv:{slug}` и `source_id=ukase-326` остаются; 0/69 совпадений не пишет.
- Реестр городов Wikidata в [`data/curated/cities-major.csv`](data/curated/cities-major.csv): P31 city/town in Russia Q7930989, P17=Q159. Около 1.1 тыс. строк, не все 1 126 городов России (ruwiki 13.05.2026) и не полный ОКТМО; без Крыма/новых субъектов. Имя файла историческое.
- Реестр площадей Wikidata в [`data/curated/agoronyms.csv`](data/curated/agoronyms.csv): P31=Q174782, P17=Q159. Около 540 строк, не все площади России и не ОМК УМ Москвы. Красная площадь сохранена.
- Реестр дорог и ЖД Wikidata в [`data/curated/dromonyms.csv`](data/curated/dromonyms.csv): P31=Q34442 и Q728937 ruwiki, P17=Q159. Около 630 строк, не перечень федеральных трасс ПП № 928 и не OSM. Транссиб и БАМ сохранены.
- Реестр сёл и пгт Wikidata в [`data/curated/villages.csv`](data/curated/villages.csv): P31=Q15078955 (пгт) и Q532 (village), P17=Q159. Около 33 тыс. строк, не ГКГН и не все сельские населённые пункты России (Росстат). Хутора Q5084 нет; `type_id=village` и у пгт. Бородино и Вёшенская сохранены.
- Реестр гидронимов Wikidata в [`data/curated/hydronyms-major.csv`](data/curated/hydronyms-major.csv): P31 озеро Q23397 и река Q4022 ruwiki, P17=Q159. Около 26 тыс. строк, не ГКГН и не все реки России. Моря Q165 сохранены FILL_IF_EMPTY; Волга и Дон — gold.
- Реестр оронимов Wikidata в [`data/curated/oronyms-major.csv`](data/curated/oronyms-major.csv): P31 гора Q8502, хребет Q46831, вулкан Q8072, остров Q23442, полуостров Q34763, P17=Q159. Около 13 тыс. строк, не ГКГН и не все горы России. Остров/полуостров — `insulonym`. Эльбрус, Уральские горы и Сахалин сохранены.
- Join Wikidata на [`data/curated/agencies-foiv.csv`](data/curated/agencies-foiv.csv): 57 из 69 строк получили `wd` (P31 Q4481741/Q4481675/Q14944295). Не harvest: 69 `foiv:{slug}`, `source_id=ukase-326`. Не все ФОИВ России.

### Changed
- [`scripts/sync.py`](scripts/sync.py) `--source wikidata`: known-ids SPARQL `VALUES` по уже известным Q-id сёл, гидронимов, оронимов, площадей и дромонимов (как и городов/МО/годонимов/агентств). `inserted=0`: неизвестные Q-id из SPARQL не вставляет. Daily `kind=none`.
- [`data/mappings/wikidata.yaml`](data/mappings/wikidata.yaml) — `class_map` и списки `city_p31` / `village_p31` / `agoronym_p31` / `dromonym_p31` / `hydronym_p31` / `oronym_p31` (P31 Wikidata, не Росстат/ГКГН). Хутора Q5084 в карте есть, в harvest VALUES нет.
- [`docs/USAGE.md`](docs/USAGE.md) §3.1 и [`docs/taxonomy.md`](docs/taxonomy.md): `cities-major` больше не сид pop≥100k, а harvest Wikidata Q7930989 (не Росстат).
- [`docs/USAGE.md`](docs/USAGE.md) §3.2: площади больше не «малые сиды», а harvest Wikidata Q174782 (не ОМК УМ Москвы).
- [`docs/USAGE.md`](docs/USAGE.md) §3.2: дромонимы больше не «малые сиды», а harvest Wikidata Q34442/Q728937 (не ПП № 928, не OSM).
- [`docs/USAGE.md`](docs/USAGE.md) §3.2: сёла/пгт больше не «малые сиды», а harvest Wikidata Q15078955/Q532 (не ГКГН, не Росстат).
- [`docs/USAGE.md`](docs/USAGE.md) §3.2 и [`docs/taxonomy.md`](docs/taxonomy.md): гидронимы больше не «крупный сид», а harvest Wikidata Q23397/Q4022 (не ГКГН).
- [`docs/USAGE.md`](docs/USAGE.md) §3.2 и [`docs/taxonomy.md`](docs/taxonomy.md): оронимы больше не «крупный сид», а harvest Wikidata Q8502/Q46831/Q8072/Q23442/Q34763 (не ГКГН).
- [`scripts/lib/harvest.py`](scripts/lib/harvest.py): `shard_query` / `fetch_sharded` / `region_wd_qids`. `wall_sec=0` обходит все 89 субъектов; `seed_municipalities.py` зовёт с `wall_sec=600`.
- Онтология: DEC-SEED-006 (города Wikidata), DEC-SEED-007 (сёла/пгт Wikidata), DEC-SEED-008 (площади Wikidata), DEC-SEED-009 (дороги/ЖД Wikidata), DEC-SEED-010 (гидронимы Wikidata), DEC-SEED-011 (оронимы Wikidata); DEC-SEED-001/002 остаются `accepted`.
- Онтология: DEC-SEED-012 (ФОИВ — join Wikidata, не harvest, не все ФОИВ России) и DEC-SEED-013 (`sync.py --source wikidata` known-ids, `inserted=0`, daily `kind=none`).
- [`CYCLE_PLAN.md`](CYCLE_PLAN.md) и [`docs/USAGE.md`](docs/USAGE.md): покрытие городов, сёл, гидронимов и оронимов — Wikidata, не Росстат/ГКГН и не «все X России». Формула «не все X России» стоит в одном предложении с Wikidata, Росстатом или ГКГН.

## [2026.09.17] - 2026-09-17

Harvest МО и микротопонимов Wikidata. Теги `2026.09.11`, `2026.09.12`, `2026.09.13`, `2026.09.14`, `2026.09.15` и `2026.09.16` не двигались.

### Added
- CLI `python scripts/seed_municipalities.py` и SPARQL-указатель [`data/raw/wikidata/municipalities-ru.sparql`](data/raw/wikidata/municipalities-ru.sparql) (P31 МО Wikidata, не ОКТМО/ГАР).
- CLI `python scripts/seed_microtoponyms.py` и SPARQL-указатель [`data/raw/wikidata/microtoponyms-ru.sparql`](data/raw/wikidata/microtoponyms-ru.sparql) (парк/пещера/овраг/урочище/поле Wikidata, не ГКГН).
- Реестр микротопонимов Wikidata в [`data/curated/microtoponyms.csv`](data/curated/microtoponyms.csv): parks+caves+овраг+урочище+поле, плюс 17 курируемых extras (леса, бархан, Провал) не как массовые классы. Около 890 строк, не ГКГН и не все микротопонимы России.
- Реестр МО Wikidata в [`data/curated/municipalities.csv`](data/curated/municipalities.csv): P31 городской округ Q13626398, муниципальный округ Q3350075, район Q2198484 / Q60849925, внутригородское Q27587207, городское поселение Q2661988, сельское поселение Q634099 (все сели). Около 21.6 тыс. строк, не ОКТМО/ГАР и не все МО России (Росстат 01.01.2026 = 13 698).
- Образ `ghcr.io/unhexx/toponym:2026.09.17` (и `:CalVer`) публикуется CI на push в `main`. `compose.yaml` пинит этот тег.

### Changed
- Перезапуск [`scripts/seed_hodonyms.py`](scripts/seed_hodonyms.py) после реестра МО: улицы с P131* на район/округ получают `parent_id` (Wikidata, не ФИАС). Около 920 parent=МО, iso-родители почти ушли; покрытие по-прежнему Wikidata, не все улицы России.
- [`scripts/sync.py`](scripts/sync.py) `--source wikidata --apply`: SPARQL `VALUES` по известным Q-id **всех** seed-таблиц (города, МО, годонимы, микротопонимы, …), fill-if-empty `lat`/`lon`/`geonames`/`oktmo`/`name_en`. Новые Q-id не вставляет. `detector.kind=none` не флипает daily. JSON запроса в git не кладётся.
- SPARQL/upsert хелперы годонимов вынесены в [`scripts/lib/harvest.py`](scripts/lib/harvest.py) (параметры `required`/`last`/`specs`/`rels`/`fill`). CLI и stdout `python scripts/seed_hodonyms.py` те же; канон не трогали.
- [`data/mappings/wikidata.yaml`](data/mappings/wikidata.yaml) — `class_map` и списки `municipality_p31` / `microtoponym_p31` для harvest МО и микротопонимов.
- [`docs/USAGE.md`](docs/USAGE.md) §3.1 и [`docs/taxonomy.md`](docs/taxonomy.md): муниципалитеты и микротопонимы больше не «десятки», а harvest Wikidata (не полный ОКТМО / не ГКГН).
- Онтология: DEC-SEED-004 (МО Wikidata) и DEC-SEED-005 (микротопонимы Wikidata); DEC-SEED-001 остаётся `accepted`. Daily 48ч SPARQL — сигнал перезапустить `seed_*.py`, не дельта `daily.py`.

## [2026.09.16] - 2026-09-16

Реестр годонимов Wikidata. Теги `2026.09.11`, `2026.09.12`, `2026.09.13`, `2026.09.14` и `2026.09.15` не двигались.

### Added
- Реестр годонимов из Wikidata (DEC-SEED-003): SPARQL [`data/raw/wikidata/hodonyms-ru.sparql`](data/raw/wikidata/hodonyms-ru.sparql) (P31 улица/бульвар/проспект/переулок/набережная, P17=Q159, без площадей), upsert `python scripts/seed_hodonyms.py` по `wd:Q…`. JSON/CSV запроса в git не кладётся. В каноне — около 15 тыс. строк (Wikidata), не ФИАС и не все улицы России.
- Образ `ghcr.io/unhexx/toponym:2026.09.16` (и `:CalVer`) публикуется CI на push в `main`. `compose.yaml` пинит этот тег.

### Changed
- [`data/curated/hodonyms.csv`](data/curated/hodonyms.csv) — уже не демо-сиды DEC-SEED-001, а таблица улиц Wikidata. Daily-синк по-прежнему `known_ids_only`. Склонения новых строк — `review=needs_review`, без pymorphy.
- Harvest годонимов берёт все P31 из маппинга, не только улицу: бульвар Q54114, проспект Q628179, переулок Q1251403, набережная Q537127. SPARQL — `VALUES ?type`; `seed_hodonyms.py` гоняет типы по одному (таймаут улицы не съедает остальные). Покрытие по-прежнему Wikidata, не ФИАС.

## [2026.09.15] - 2026-09-15

Витрина README и оглавление документации. Теги `2026.09.11`, `2026.09.12`, `2026.09.13` и `2026.09.14` не двигались.

### Changed
- README — витрина: схемы mermaid, полный каталог документации, бейджи, автор Evgeniy Chistyakov / Unhandled Exception (DAO EXCEPTION EXPERT). Оглавление — `docs/README.md`. `CITATION.cff` и `pyproject.toml` authors/urls.

### Added
- Образ `ghcr.io/unhexx/toponym:2026.09.15` (и `:CalVer`) публикуется CI на push в `main`. `compose.yaml` пинит этот тег.

## [2026.09.14] - 2026-09-14

http_dated без GET при текущем курсоре, журнал из `journal_fields`, daily без `*_fn`. Теги `2026.09.11`, `2026.09.12` и `2026.09.13` не двигались.

### Removed
- Мёртвый SHA-стек HTML: `normalize_html`, `fingerprint_text` и четыре regex в детекторах. Kind `page_fingerprint` остаётся (MediaWiki lastrevid / ETag).
- Журнал daily: один путь counts через `UpsertCounts.journal_fields()`. Убраны `journal_counts_from_sync_files`, fallback `inserted+updated`, `sync_json` и CLI `journal.py`.
- `run_daily` больше не принимает шесть `*_fn`: зовёт `check_catalog` / `run_sync` / `validate_tree` / `rebuild_index` / `stamp_catalog_checked_at` / `revert_data` напрямую. Sync только `changed and not error`.

### Fixed
- `http_dated`: курсор сравнивается с вчерашней UTC-датой до GET mods/deletes. Текущий watermark — без сети; таймаут уже актуального дампа не блокирует check.
- Daily: после `validate==0` CSV и журнал с реальными counts остаются даже если FTS-индекс падает. Индекс производный (gitignore); драйвер не валит GHA из-за него.

### Added
- Образ `ghcr.io/unhexx/toponym:2026.09.14` (и `:CalVer`) публикуется CI на push в `main`. `compose.yaml` пинит этот тег.

## [2026.09.13] - 2026-09-13

Daily-драйвер, честные курсоры и журнал. Теги `2026.09.11` и `2026.09.12` не двигались.

### Removed
- Из дерева продукта убраны служебные файлы внутреннего цикла разработки. Правила канона — в `CONTRIBUTING.md`; ежедневный прогон — `docs/DAILY_UPDATE.md`.

### Fixed
- `blocking` в отчёте check только на строках с `error`; неблокирующие указатели (ГКГН/ГАР) задаются в `catalog.yaml` (`blocking: false`), а не эвристикой vendor+http_head.
- Каталог больше не патчится regex: load → правка mapping → YAML dump.
- `ukase-326`: курсор — MediaWiki `lastrevid` (или ETag), не SHA Wikipedia-хрома. `sync --apply` без `--manual-file` не пишет `cursor` в каталог.
- Журнал daily: `records_upserted` / `records_deprecated` берутся из `UpsertCounts` sync (`inserted+updated` / `deprecated`), а не захардкоженные нули.
- `http_dated`: `changed` только если есть RU-строки **и** курсор каталога ещё не равен вчерашней UTC-дате. Повторный check в тот же день (курсор уже yesterday) не даёт exit 10.
- Daily: таймаут `http_head` у указателей (Росреестр/ФИАС) больше не даёт `check.py` код 2 и не блокирует GeoNames. Журнал `data/sources/runs/` пишется и при коде 2; `workflow_dispatch` — `--ref main`, не `main~`.

### Changed
- Списки CSV мест — только `load_place_relpaths` / `load_index_relpaths`, без модульных `__getattr__`.
- Daily: `scripts/daily.py` ведёт check → sync только changed → validate/index → журнал с `UpsertCounts` → stamp на no-op. `.github/workflows/daily.yml` — install, запуск драйвера, commit-if-diff.
- Ручная приёмка высокочастотных склонений в `gold`: 15 городов-миллионников плюс Тольятти/Улан-Удэ (нескл.) и Ярославль, Саратов, Иркутск, Владивосток, Томск, Тюмень; творительный Воронежа — **Воронежем**. Аббревиатуры КС РФ, ВС РФ, АП, Совбез, Генпрокуратура, СК России, Банк России, ЦИК России, Счётная палата. Норма в `source` (`Розенталь; Грамота.ру`). Остаток городов/полных имён ФОИВ — `needs_review`. Фикстуры DECLENSIONS.md не переписывались.

### Added
- Образ `ghcr.io/unhexx/toponym:2026.09.13` (и `:CalVer`) публикуется CI на push в `main`. `compose.yaml` пинит этот тег, `build` остаётся опциональным. Обновление без сборки: `docker compose pull && docker compose up`.
- CI: отдельный job `compose` (`pytest tests/test_compose_smoke.py`, timeout 20 мин; ящик поднимает сам тест). Unit-job `pytest -m "not compose"` без Docker.
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
- DEC-TEMPLATE-001 — внешние шаблоны разработки не вендорятся в git.
- Онтология: DEC-ONT-001 — только Outpost `ontology/ontology.json`; keep-out A–J, L закрыты DEC-* (дамп, шаблоны, hflabs, гео, P1).
- HTTP: DEC-SERVE-002 — публичный Internet API вне scope; host publish только `127.0.0.1:8099`, не `0.0.0.0`.
- Таксономия: DEC-TAX-001 — `toponym` / `oikonym` / `hydronym` не переименовывать; `validate.py` держит корень.
- Склонения: DEC-DECL-002 — уникальность `(id, lemma)`; `id` не unique; золото ФОИВ с двумя леммами не переписывать.
- Склонения: DEC-DECL-001 — pymorphy/Natasha не золото; `validate.py` отклоняет `review=gold` с источником-морфоанализатором; канон не переписывается.
- GeoNames: DEC-GN-001 — sync только match колонки `geonames`; `validate.py` отклоняет `id=gn:…` в местах; немаппленные mods остаются `skipped_unmapped`.
- README: бейджи shields.io (MIT, CalVer `2026.09.12`, CI `ci.yml`, Python 3.12+, Docker Compose), ссылки на `docs/USAGE.md`, CHANGELOG, SOURCES, презентацию и релиз; старт хоста (`.venv`) и `docker compose up --build` с `127.0.0.1:8099/healthz`.
- `scripts/serve.py`: `PACKAGE_VERSION` = `2026.09.12` (`GET /healthz` больше не отдаёт `2026.09.09`).

### Fixed
- README: дефолт «только реестр» — venv + `pip install -e ".[dev]"`. Daily GHA ставит пакет так же.
- Золото «Волга» (`wd:Q626`): родительный падеж **Волги**, не «Волгы» (Розенталь; `docs/DECLENSIONS.md`). Ручной патч по id, без автосклонения.
- Daily GHA: установка `pip install -e ".[dev]"`. Журнал `data/sources/runs/YYYY-MM-DD.json` пишется при check 0/10; `checked_at` сдвигается, если устарел.
- SSOT: CYCLE_PLAN DoD — 19 resources; онтология `calver` = `2026.09.12`; ADR помечен историческим снимком v1.

## [2026.09.11] - 2026-09-11

Loopback JSON-поиск и Docker Compose-ящик на `127.0.0.1:8099` (DEC-SERVE-001). Включает v1.1: `http_dated` только по RU-строкам.

### Added
- Loopback JSON-поиск `scripts/serve.py` на `127.0.0.1:8099` (`/healthz`, `/v1/search`, `/v1/records`).
- One-shot Docker Compose: `docker compose up --build`, Python 3.12, `validate → index → serve`.
- Решение `DEC-SERVE-001`: stdlib HTTP, не Datasette/FastAPI и не посторонний стек.

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
- Исполняемый ежедневный промпт `docs/DAILY_UPDATE.md` (check → sync → validate → index; журнал `data/sources/runs/`).
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

[Unreleased]: https://github.com/unhexx/toponym/compare/2026.09.17...HEAD
[2026.09.17]: https://github.com/unhexx/toponym/releases/tag/2026.09.17
[2026.09.16]: https://github.com/unhexx/toponym/releases/tag/2026.09.16
[2026.09.15]: https://github.com/unhexx/toponym/releases/tag/2026.09.15
[2026.09.14]: https://github.com/unhexx/toponym/releases/tag/2026.09.14
[2026.09.13]: https://github.com/unhexx/toponym/releases/tag/2026.09.13
[2026.09.12]: https://github.com/unhexx/toponym/releases/tag/2026.09.12
[2026.09.11]: https://github.com/unhexx/toponym/releases/tag/2026.09.11
[2026.09.09]: https://github.com/unhexx/toponym/releases/tag/2026.09.09
