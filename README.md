# Toponym — реестр российских топонимов

Открытый структурированный реестр топонимов Российской Федерации: населённые пункты, субъекты, гидронимы, оронимы, урбанонимы, ведомства и службы, таблицы склонений.

Канон — UTF-8 CSV в git (Frictionless Tabular Data Package). Индекс SQLite FTS5 собирается локально и в git не кладётся.

Лицензия репозитория: [MIT](LICENSE). Сырьё источников хранит свои лицензии — см. [`docs/SOURCES.md`](docs/SOURCES.md) и [`data/sources/catalog.yaml`](data/sources/catalog.yaml).

## Пятиминутный старт

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
bash Agent-Init.sh
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/validate.py
python scripts/check.py --json
python scripts/index.py
```

Альтернатива установке: `uv pip install -e ".[dev]"` в том же `.venv`.

Ожидаемо: `validate.py` печатает `ok` и выходит 0. `check.py --json` ходит в сеть (коды 0 / 10 / 2). `index.py` пишет `knowledge/registry.db` (gitignored).

## One-shot (Docker Compose)

Если на хосте нет CPython 3.12 — тот же канон поднимается ящиком:

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
docker compose up --build
```

Слушает только loopback: http://127.0.0.1:8099/healthz  
Поиск: http://127.0.0.1:8099/v1/search?q=Волга  

Не стартует SearXNG, Ollama и pxpipe. Порты 8080 / 8100 / 8110 / 8112 на хосте свободны.

На хосте без Docker: `python scripts/validate.py && python scripts/index.py && python scripts/serve.py` (bind `127.0.0.1:8099`).

## Дерево

```
data/
  curated/          # канонические таблицы (UTF-8 CSV)
  declensions/      # склонения: nom gen dat acc ins pre loc2
  raw/              # указатели источников + SOURCE.md (не смешивать с curated)
  sources/          # каталог источников и даты проверок
schema/             # JSON Schema колонок
scripts/            # check, sync, validate, index, serve
ontology/           # overlay DEC-REG-001, Source, Mapping
docs/               # методология, таксономия, лицензии
agents/             # промпт ежедневного обновления
```

Канонический формат: **CSV UTF-8, LF, заголовок обязателен**. Идентификаторы стабильны. Крупные дампы (ГАР/ФИАС, GeoNames `RU.zip`) **не вендорятся**.

## Типы топонимов

См. [`data/curated/types.csv`](data/curated/types.csv) и [`docs/taxonomy.md`](docs/taxonomy.md).

Основные классы: хоронимы · ойконимы · гидронимы · оронимы · годонимы · урбанонимы · инсулонимы · ведомства.

Верхний уровень типов — `toponym` (не «Торопум»).

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

## Скрипты

```bash
python scripts/check.py --json          # детекторы; 0 / 10 / 2
python scripts/sync.py --source ID      # dry-run; --apply пишет
python scripts/validate.py              # frictionless + инварианты
python scripts/index.py                 # knowledge/registry.db FTS5
python scripts/serve.py                 # loopback JSON, 127.0.0.1:8099
```

Поиск по индексу: `MATCH 'Волга'` (гидроним), `MATCH 'МВД'` (`foiv:mvd`).

## Автоматизация

- GitHub Actions: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — pytest, ruff, validate.
- Daily: [`.github/workflows/daily.yml`](.github/workflows/daily.yml) — механический refresh.
- Куратор: [`agents/DAILY_UPDATE.md`](agents/DAILY_UPDATE.md) — check → sync → validate → index; без пустого коммита.

## Цитирование

См. [`CITATION.cff`](CITATION.cff). Версия: `2026.09.11`.
