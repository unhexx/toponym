# Локальные реестры: дизайн и дорожная карта

**Дата:** 2026-09-09  
**Статус:** исторический снимок ADR DEC-REG-001 и плана v1. Сиды и скрипты уже на `main` (тег `2026.09.09`); loop 2 — тег `2026.09.11`. Живой план: `CYCLE_PLAN.md`. Backlog: GitHub #13.  
**Контекст:** `unhexx/toponym` — локальный реестр топонимов (Frictionless CSV + derived SQLite FTS).

---

## 1. Задача

Нужен **качественный локальный реестр** (не дашборд и не вендор дампов), в котором:

1. Все реестры лежат в одном git-репозитории.
2. Структура удобна любому приложению (CSV / JSON / SQLite / HTTP-less API).
3. У каждого реестра указаны источники, лицензии, даты проверки.
4. Схемы источников сопоставлены с канонической моделью.
5. Есть простые скрипты: «есть ли обновление?» → «обнови локальный реестр».
6. Разработка до v1 идёт **одним полным циклом** по плану, а не бесконечным daily-no-op.

На дату ADR (2026-09-09) `unhexx/toponym` был зародышем (Frictionless `datapackage.json`, `catalog.yaml`, таксономия): сиды ещё не были закоммичены, curated-таблиц и скриптов проверки не было. Это уже не текущее состояние: v1 tagged `2026.09.09`, loop 2 — `2026.09.11`.

---

## 2. Исследование и выбор решения

### 2.1 Кандидаты

| Вариант | Суть | Минусы для этой задачи |
|---|---|---|
| A. Только SQLite / DuckDB | Быстрый поиск | Плохо диффится в git, неудобен чужим приложениям без драйвера |
| B. Только GeoJSON / PostGIS | Гео-натив | Тяжело для ФОИВ, склонений, кодов; вендорит объём |
| C. CKAN / Dataverse | Каталог-сервер | Сервер = не local-first, избыточно |
| D. Google OKF (markdown concepts) | Провенанс, stale_after | Слабый tabular interchange, нет Table Schema |
| E. **Frictionless Tabular Data Package + git + derived SQLite + ontology overlay** | CSV UTF-8 как канон, `datapackage.json` как контракт, catalog как источники, SQLite как индекс | Нужна дисциплина upsert и не вендорить >10 МБ |

### 2.2 Решение (DEC-REG-001)

**Канон = git + Frictionless Tabular Data Package.**  
**Индекс = локальный SQLite FTS (derived, в `.gitignore` или `knowledge/`).**  
**Смысловой слой = онтология Source / Registry / Resource / Mapping / Check / Decision.**  
**Сырьё с ODbL / CC-BY-SA = только `data/raw/<source>/` + SOURCE.md.**  
**Дампы >10 МБ и полный ГАР/ФИАС не вендорятся** — только указатель + хеш + скрипт импорта.

Почему это лучшее решение:

- Любое приложение читает CSV без SDK (Python, Go, Excel, DuckDB, pandas, jq).
- `datapackage.json` + Table Schema дают машинную валидацию (`frictionless validate`).
- Git даёт историю, review, CalVer, воспроизводимость.
- Local-first: поиск не ходит в облако на каждый запрос.
- Совпадает с уже выбранным профилем `toponym`.
- Провенанс OKF (`sources`, `stale_after`, `status`) переносим в `catalog.yaml` и в ontology.json, не ломая табличный канон.

Ссылки практик: Frictionless Data Package / Table Schema / Tabular Data Resource; OKF v0.2 provenance; Outpost Memory (не плодить второй формат онтологии).

---

## 3. Целевая структура репозитория

Рекомендуемый путь: развивать **`unhexx/toponym` как первый домен** внутри того же репо, с заделом `domains/` так, чтобы второй реестр (коды регионов, ФОИВ, улицы) добавлялся копированием пакета, а не форком.

```
toponym/                          # git SSOT
├── CONTRIBUTING.md
├── TASK_SPECIFICATION.md         # этот документ, сжатый контракт v1
├── TASK_SPECIFICATION.md
├── datapackage.json              # пакет верхнего уровня
├── catalog.yaml                  # источники + детекторы обновлений
├── CHANGELOG.md                  # CalVer YYYY.MM.DD
├── schema/
│   ├── registry.schema.json      # запись канона
│   ├── catalog.schema.json
│   ├── mapping.schema.json
│   └── table/
│       ├── types.schema.json
│       ├── places.schema.json
│       ├── agencies.schema.json
│       └── declensions.schema.json
├── data/
│   ├── curated/                  # канон, патч по stable id
│   │   ├── types.csv
│   │   ├── federal-districts.csv
│   │   ├── regions.csv
│   │   ├── cities-major.csv
│   │   ├── hydronyms-major.csv
│   │   ├── oronyms-major.csv
│   │   ├── agencies-foiv.csv
│   │   └── agencies-other.csv
│   ├── declensions/              # золото без автоперезаписи
│   ├── mappings/                 # source_field → canonical_field
│   │   ├── geonames.yaml
│   │   ├── gkgn.yaml
│   │   ├── fias-pointer.yaml
│   │   ├── hflabs-region.yaml
│   │   └── ukase-326.yaml
│   ├── raw/                      # лицензионно-ограниченное сырьё
│   │   └── <source-id>/SOURCE.md
│   └── sources/
│       └── catalog.yaml          # symlink или единственный catalog.yaml
├── scripts/
│   ├── check.py                  # есть ли обновление? JSON-отчёт
│   ├── sync.py                   # fetch allowed + upsert curated
│   ├── validate.py               # frictionless + инварианты
│   └── index.py                  # пересобрать knowledge/registry.db
├── knowledge/                    # derived, не обязательно в git
│   ├── registry.db               # SQLite FTS5
│   └── LAST_INDEX
├── ontology/
│   └── ontology.json             # сущности Source, Registry, Mapping…
├── agents/
│   └── DAILY_UPDATE.md
├── docs/DAILY_UPDATE.md
│   ├── PLAN.md
│   ├── TODO.md
│   └── LOOP_STATE.md
└── tests/
    ├── test_check.py
    ├── test_upsert.py
    └── fixtures/
```

Правила файлов (CONTRIBUTING.md):

- UTF-8, LF, CSV delimiter = запятая, заголовок обязателен.
- Не переписывать CSV целиком; upsert по stable id.
- Не удалять строки: `status=deprecated` + `replaced_by`.
- `name_yo` хранит ё; `name_ru` нормализован (ё→е только там).
- Склонения без ручной проверки — только `review=true`.

---

## 4. Каноническая модель данных

### 4.1 Общая запись реестра (`places` / `agencies` / хоронимы)

Минимальный набор колонок (единый профиль, лишние поля пустые):

| Поле | Тип | Смысл |
|---|---|---|
| `id` | string PK | стабильный: `wd:Q649`, `gn:524901`, `iso:RU-MOS`, `foiv:mvd`, `gkgn:…` |
| `id_scheme` | string | `wikidata` / `geonames` / `iso3166-2` / `fias` / `gkgn` / `abbr` / `local` |
| `type_id` | string FK | `data/curated/types.csv` |
| `name_ru` | string | нормализованное |
| `name_yo` | string | с ё |
| `name_en` | string | |
| `abbr` | string | ЦФО, МВД |
| `parent_id` | string | иерархия |
| `admin1` | string | код субъекта |
| `lat` / `lon` | number | WGS84, опционально |
| `wd` / `geonames` / `fias` / `oktmo` / `iso` | string | внешние ключи |
| `status` | enum | `active` / `deprecated` |
| `replaced_by` | string | |
| `source_id` | string FK | catalog |
| `source_rev` | string | дата или SHA источника |
| `updated_at` | date | |
| `notes` | string | |

### 4.2 Сопоставление схем источников

| Источник | Ключ | Имя | Класс | Гео | Куда в каноне |
|---|---|---|---|---|---|
| GeoNames dump | `geonameId` | `name` / `asciiname` / `alternatenames` | `featureClass` A/P/H/T/L | lat/lng | `id=gn:{id}`, `type_id` через карту класса |
| GeoNames modifications-YYYY-MM-DD | то же | то же | то же | то же | upsert; deletes → deprecated |
| ГКГН Росреестр | регистрационный номер | наименование | вид объекта | при наличии | `id=gkgn:{n}` |
| ФИАС/ГАР | `OBJECTGUID` | `NAME` + `TYPENAME` | уровень | нет в указателе | **не вендорить**; mapping-pointer |
| hflabs/region | FIAS + ISO | name | region | — | субъекты |
| hflabs/city | FIAS | name | city | — | города |
| epogrebnyak/ru-cities | name + region | city | P | — | cities-major |
| mfursov/russian-cities | name | склонения | — | — | declensions, review=true если не золото |
| Указ №326 + №522 | аббревиатура / полное имя | ФОИВ | agency | — | agencies-foiv |
| Wikidata P17=Q159 | Q-id | ru label | instanceof | P625 | внешний ключ `wd` |

Файл `data/mappings/<source>.yaml`:

```yaml
source_id: geonames-ru
stable_id: "gn:{geonameId}"
fields:
  name: name
  name_ascii: asciiname
  lat: latitude
  lon: longitude
  geonames_class: featureClass
class_map:
  P: oikonym
  A: choronym
  H: hydronym
  T: oronym
  L: microtoponym
filter:
  country_code: RU
  feature_class: [A, P, H, T, L]
delete_policy: deprecate
```

---

## 5. Каталог источников и детекторы обновлений

`catalog.yaml` — единственный SSOT дат. Расширение относительно текущего файла:

```yaml
updated: 2026-09-09
sources:
  - id: geonames-ru
    url: https://download.geonames.org/export/dump/RU.zip
    license: CC-BY-4.0
    vendor: false
    max_vendor_bytes: 10485760
    detector:
      kind: http_dated
      urls:
        - https://download.geonames.org/export/dump/modifications-{yesterday}.txt
        - https://download.geonames.org/export/dump/deletes-{yesterday}.txt
      also: last_modified_header   # на RU.zip
    checked_at: 2026-09-09
    cursor: "2026-09-08"
  - id: hflabs-region
    url: https://github.com/hflabs/region
    license: CC-BY-SA-4.0
    detector:
      kind: github_commits
      repo: hflabs/region
      since: checked_at
    checked_at: 2026-09-09
    cursor: "<sha>"
  - id: ukase-326
    detector:
      kind: page_fingerprint
      urls:
        - https://ru.wikipedia.org/wiki/Структура_федеральных_органов_исполнительной_власти_России_(с_2024)
      note: "структурный указ после №522 — ручной gate"
```

Типы детекторов (реализуются в `scripts/check.py`):

1. **http_head** — `ETag` / `Last-Modified` / `Content-Length`.
2. **http_dated** — шаблон даты GeoNames.
3. **github_commits** — `commits?since=` + сравнение SHA с `cursor`.
4. **page_fingerprint** — SHA-256 нормализованного текста (ФОИВ/Вики).
5. **none** — только `checked_at` (официальный PDF указа).

Выход `check.py --json`:

```json
{
  "as_of": "2026-09-09T10:00:00Z",
  "sources": [
    {"id": "geonames-ru", "changed": false, "reason": "0 RU rows in mods"},
    {"id": "hflabs-region", "changed": false, "reason": "sha match"}
  ],
  "changed_count": 0
}
```

Код выхода: `0` нет изменений, `10` есть изменения, `2` ошибка сети/схемы.

---

## 6. Конвейер обновления

```
check.py  →  (changed?)  →  sync.py  →  validate.py  →  index.py
                 │
                 └ no  →  обновить только checked_at (не пустой коммит:
                           либо запись в data/sources/runs/YYYY-MM-DD.json,
                           либо no-op без commit — как сейчас)
```

`sync.py` правила:

- Скачивать в `data/raw/` только то, что `vendor: true` и `< 10 МБ`.
- Иначе работать по дельте (GeoNames modifications) или по указателю.
- Upsert по `id`; delete запрещён.
- Gold-склонения не трогать.
- Писать `source_rev`, `updated_at`.
- Коммит: `chore(data): daily refresh YYYY-MM-DD (N records, sources: …)`.

`validate.py`:

- `frictionless validate datapackage.json`
- уникальность `id`
- FK `type_id` ∈ types.csv
- `status` enum
- нет «Торопум»
- CSV UTF-8 LF

`index.py`:

- SQLite FTS5 по `name_ru`, `name_yo`, `abbr`, `wd`
- таблица `sync_meta(source_id, checked_at, cursor, hash)`
- это слой `local-knowledge-ingestion`

Онтология (`structured-memory-ontology`, формат Outpost):

| Тип | Пример id | Смысл |
|---|---|---|
| Project | `PRJ-TOPONYM` | реестр |
| Artifact | `ART-CATALOG` | catalog.yaml |
| Decision | `DEC-REG-001` | выбор Frictionless+git |
| Source | `SRC-GEONAMES` | источник |
| Mapping | `MAP-GN-CANON` | сопоставление |
| Check | `CHK-2026-09-09` | прогон детектора |
| Risk | `RSK-FIAS-VENDOR` | запрет вендорить ГАР |
| Lesson | после цикла | no-op daily без сидов |

---

## 7. Интеграция с приложениями

Контракт v1 (без сервера):

```text
читать  data/curated/*.csv
схема   schema/table/*.json + datapackage.json
источник catalog.yaml
поиск   knowledge/registry.db  (опционально)
пакет   python -c "import frictionless, pandas"
        duckdb.read_csv_auto('data/curated/regions.csv')
```

Позже (вне v1): тонкий `scripts/serve.py` loopback; не делать публичный API в первом цикле.

---

## 8. Что не входит в v1

- Полный импорт RU.zip / ГАР.
- Автосклонения pymorphy как золото.
- Переписывание таксономии верхнего уровня.
- Merge в `main` внешнего шаблона (циклы живут на feature-ветке продукта).
- Второй формат онтологии помимо Outpost `ontology.json`.

---

## 9. Дорожная карта v1

Цель пользователя: **разовый запуск полного цикла разработки до финальной версии v1**, не вечный ежедневный прогон.

### 9.1 Bootstrap

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Разработка — узкими слайсами в git. Готово, когда сиды, скрипты и тесты зелёные.

### 9.2 Фазы INVEST (узкие слайсы)

| ID | Слайс | Acceptance | Evidence |
|---|---|---|---|
| **P0-BOOT** | PLAN, SPEC, AGENTS, catalog.schema.json | файлы на ветке, validate schema | commit |
| **P1-SEED** | сиды: ФО, субъекты, ФОИВ, крупные гидро/оро, types уже есть | datapackage resources существуют, ≥1 строка на таблицу | CSV + SHA |
| **P2-MAP** | mappings для GeoNames, ГКГН-указатель, 326, hflabs | yaml валиден mapping.schema | файлы |
| **P3-CHECK** | `scripts/check.py` по catalog | код 0 на сегодняшнем no-op GeoNames RU; JSON-отчёт | pytest + прогон |
| **P4-SYNC** | `scripts/sync.py` upsert + deprecate | фикстура 2 строки → 3-я добавлена, delete не стирает | pytest |
| **P5-VAL** | `scripts/validate.py` + frictionless | ломаный CSV падает | pytest |
| **P6-INDEX** | `scripts/index.py` SQLite FTS | поиск «Волга» / «МВД» | db + test |
| **P7-ONT** | ontology.json сущности Source/Decision/Check | валидный JSON, DEC-REG-001 | файл |
| **P8-DOCS** | README quick start, CHANGELOG Unreleased→2026.09.09, DAILY_UPDATE ссылается на check.py | человек поднимает за 5 мин | docs |
| **P9-DONE** | тесты зелёные, нет вендора >10МБ, типы верхнего уровня целы | tag | ledger |

Параллелить можно только P2 и P6 после P1; остальное последовательно. Синхроточка: после P5.

### 9.3 Definition of Done v1

- В репозитории есть все resources из текущего `datapackage.json`.
- `python scripts/check.py --json` работает без секретов.
- `python scripts/validate.py` = 0.
- Ежедневный прогон больше не «смотрит в пустоту»: либо применяет дельту, либо пишет `data/sources/runs/…` и **не** делает пустой commit.
- Онтология содержит DEC-REG-001 и список Source.
- Верхний уровень типов не сломан (`toponym`, не «Торопум»).

### 9.4 Оценка цикла

Один непрерывный прогон ролей: **полдня–день** на сиды + скрипты (не 15-минутный daily).  
Daily после v1 снова 15 минут и честный no-op, если дельты нет.

---

## 10. Риски

| Риск | Митигация |
|---|---|
| Сиды «заявлены, но не в git» — daily no-op | P1 обязателен до любых daily |
| ГКГН/Росреестр таймауты | detector http_head + ручной gate, не блокировать цикл |
| ФИАС соблазн вендорить | `vendor: false`, max_vendor_bytes, тест размера raw/ |
| CC-BY-SA hflabs в curated | либо производная MIT-совместимая выжимка, либо raw/ + указатель |
| Автосклонения ломают золото | sync не пишет в declensions без `review=true` |
| Второй формат памяти | только Outpost ontology.json |
| Пустой commit | запрет; при 0 дельты — runs-журнал или выход 0 без git |

---

## 11. Решение, которое фиксируем

1. **Канон:** Frictionless Tabular Data Package в git.  
2. **Источники:** расширенный `catalog.yaml` с детекторами.  
3. **Схемы:** Table Schema + YAML mappings.  
4. **Скрипты:** check / sync / validate / index.  
5. **Поисковый слой:** SQLite FTS + ontology overlay.  
6. **Исполнение v1:** слайсы P0–P9 на `feature/v1-local-registries` до зелёных тестов.

Следующий шаг: bootstrap §9.1 и `TASK_SPECIFICATION.md`.
