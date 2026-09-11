# Toponym — реестр российских топонимов

[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CalVer](https://img.shields.io/badge/CalVer-2026.09.12-informational.svg)](https://github.com/unhexx/toponym/releases/tag/2026.09.12)
[![CI](https://img.shields.io/github/actions/workflow/status/unhexx/toponym/ci.yml?branch=main&label=CI)](https://github.com/unhexx/toponym/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)
[![Docker Compose](https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker&logoColor=white)](compose.yaml)

Открытый структурированный реестр топонимов Российской Федерации: населённые пункты, субъекты, гидронимы, оронимы, муниципалитеты, годонимы, микротопонимы, урбанонимы, ведомства и службы, таблицы склонений.

Канон — UTF-8 CSV в git (Frictionless Tabular Data Package). Индекс SQLite FTS5 собирается локально и в git не кладётся. Поиск — только loopback `127.0.0.1:8099`.

Релиз: [`2026.09.12`](https://github.com/unhexx/toponym/releases/tag/2026.09.12). Лицензия репозитория: [MIT](LICENSE). Сырьё источников хранит свои лицензии — [`docs/SOURCES.md`](docs/SOURCES.md), [`data/sources/catalog.yaml`](data/sources/catalog.yaml).

## Документация

| | |
|---|---|
| [docs/USAGE.md](docs/USAGE.md) | поиск и склонения (HTTP и офлайн CSV) |
| [docs/](docs/) | методология, таксономия, дизайн, презентация |
| [CHANGELOG.md](CHANGELOG.md) | история релизов (CalVer `YYYY.MM.DD`) |
| [docs/SOURCES.md](docs/SOURCES.md) | лицензии источников и границы вендора |
| [Презентация 2026.09.11](docs/presentation/toponym-2026.09.11.md) | продуктовая колода |
| [Релиз 2026.09.12](https://github.com/unhexx/toponym/releases/tag/2026.09.12) | тег и GitHub Release |

## Пятиминутный старт (хост)

CPython 3.12+. Для канона CSV + поиск шаблон `agentic_loop_template` **не нужен**:

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/validate.py
python scripts/check.py --json
python scripts/index.py
python scripts/serve.py
```

После `pip install` те же команды на PATH: `toponym-validate`, `toponym-check`, `toponym-index`, `toponym-serve`. `python scripts/*.py` не ломается.

Альтернатива: `uv venv .venv && source .venv/bin/activate && uv pip install -e ".[dev]"`.

Полный harness-цикл — только если рядом sibling `../agentic_loop_template`: `bash Agent-Init.sh`. Без шаблона тот же скрипт ставит `.[dev]` и не падает.

Ожидаемо: `validate.py` печатает `ok` и выходит 0. `check.py --json` ходит в сеть (коды 0 / 10 / 2). `index.py` пишет `knowledge/registry.db` (gitignored). `serve.py` слушает `127.0.0.1:8099`.

Проверка:

- http://127.0.0.1:8099/healthz
- http://127.0.0.1:8099/v1/search?q=Волга

## One-shot (Docker Compose)

Если на хосте нет CPython 3.12 — тот же канон поднимается ящиком.

Первый запуск:

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
docker compose up --build
```

Обновление уже клонированного репозитория:

```bash
git pull && docker compose up --build
```

Слушает только loopback: http://127.0.0.1:8099/healthz  
Поиск: http://127.0.0.1:8099/v1/search?q=Волга  

Не стартует SearXNG, Ollama и pxpipe. Порты 8080 / 8100 / 8110 / 8112 на хосте свободны.

На хосте без Docker: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`, затем `toponym-validate && toponym-index && toponym-serve` (или `python scripts/validate.py && python scripts/index.py && python scripts/serve.py`; bind `127.0.0.1:8099`).

## Дерево

```
data/
  curated/          # канонические таблицы (UTF-8 CSV)
  declensions/      # склонения: nom gen dat acc ins pre loc2
  raw/              # указатели источников + SOURCE.md (не смешивать с curated)
  sources/          # каталог источников и даты проверок
schema/             # JSON Schema колонок
scripts/            # check, sync, validate, index, serve, fetch_dump
ontology/           # overlay DEC-REG-001, Source, Mapping
docs/               # методология, таксономия, лицензии, презентация
agents/             # промпт ежедневного обновления
```

Канонический формат: **CSV UTF-8, LF, заголовок обязателен**. Идентификаторы стабильны. Крупные дампы (ГАР/ФИАС, GeoNames `RU.zip`) **не вендорятся**.

## Типы топонимов

См. [`data/curated/types.csv`](data/curated/types.csv) и [`docs/taxonomy.md`](docs/taxonomy.md).

Основные классы: хоронимы · ойконимы · гидронимы · оронимы · годонимы · урбанонимы · инсулонимы · ведомства.

Верхний уровень типов — `toponym` / `oikonym` / `hydronym` (не «Торопум»; DEC-TAX-001).

## Источники

Сводка лицензий и правил вендора: [`docs/SOURCES.md`](docs/SOURCES.md). Каталог с детекторами: [`data/sources/catalog.yaml`](data/sources/catalog.yaml).

| Источник | Что даёт | Лицензия | В каноне |
|---|---|---|---|
| Wikidata | Q-id, имена, P625 | CC0 | сиды мест |
| Указ № 326 / № 522 | структура ФОИВ | официальный текст | `agencies-foiv.csv` |
| ISO 3166-2:RU | коды субъектов | ISO | `regions.csv` |
| GeoNames | идентификаторы, mods | CC BY 4.0 | id, не `RU.zip` |
| ГКГН | официальные названия | открытые данные | указатель |
| ФИАС / ГАР | адресная иерархия | открытые данные | указатель, без дампа |
| hflabs/region, hflabs/city | регионы и города + ФИАС | CC BY-SA 4.0 | только `data/raw/` |

## Склонения

Золотые таблицы в `data/declensions/`. Правила — [`docs/DECLENSIONS.md`](docs/DECLENSIONS.md).

Поля: `id,type_code,lemma,yo,gender,paradigm,declinable,nom,gen,dat,acc,ins,pre,loc2,review,source`.

`review`: `gold` (не перезаписывать), `needs_review` (авто без ручной проверки), `auto`.

Очередь автоформ (не канон): [`data/declensions/queue.csv`](data/declensions/queue.csv). pymorphy/Natasha не пишут `gold` (DEC-DECL-001).

Уникальность склонений — `(id, lemma)` (DEC-DECL-002); `id` в файле может повторяться.

## Скрипты

```bash
python scripts/check.py --json          # детекторы; 0 / 10 / 2
python scripts/sync.py --source ID      # dry-run; --apply пишет
python scripts/validate.py              # frictionless + инварианты
python scripts/index.py                 # knowledge/registry.db FTS5
python scripts/serve.py                 # loopback JSON, 127.0.0.1:8099
python scripts/fetch_dump.py --source geonames-ru   # RU.zip в tmp, не в git
```

Console scripts (после `pip install -e .`): `toponym-check`, `toponym-validate`, `toponym-index`, `toponym-serve`.

Поиск по индексу: `MATCH 'Волга'` (гидроним), `MATCH 'МВД'` (`foiv:mvd`).

HTTP (только GET, только loopback): `/healthz`, `/v1/search?q=…`, `/v1/records?id=…`.

## Автоматизация

- GitHub Actions: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — pytest, ruff, validate.
- Daily: [`.github/workflows/daily.yml`](.github/workflows/daily.yml) — механический refresh.
- Куратор: [`agents/DAILY_UPDATE.md`](agents/DAILY_UPDATE.md) — check → sync → validate → index; без пустого коммита.

## Цитирование

См. [`CITATION.cff`](CITATION.cff). Версия: `2026.09.12`.
