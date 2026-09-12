---
title: Toponym — реестр российских топонимов
version: "2026.09.11"
lang: ru
---

# Toponym

Реестр российских топонимов и ведомств

Колода к тегу `2026.09.11`. Актуальная витрина — [README](../../README.md).

Канон CSV в git · локальный FTS · loopback-поиск

**2026.09.11** · MIT · [github.com/unhexx/toponym](https://github.com/unhexx/toponym)

---

# Зачем

Имена мест и служб — как данные, которые можно держать у себя: без портала, без дампа ГАР и без публичного API.

- Канон — **UTF-8 CSV** в git, не база
- Индекс SQLite FTS5 **собирается локально** и в git не кладётся
- Поиск слушает только **127.0.0.1:8099**

Frictionless Tabular Data Package. Верхний тип — `toponym`.

---

# Канон CSV

Формат: **UTF-8, LF, запятая, обязательный заголовок**. Идентификаторы стабильны.

11 ресурсов `datapackage.json`:

| Таблица | Содержание |
|---|---|
| `types` | таксономия |
| `federal-districts` / `regions` | 8 округов, 89 субъектов |
| `cities-major` | крупные города |
| `hydronyms-major` / `oronyms-major` | реки, горы |
| `agencies-foiv` / `agencies-other` | ФОИВ и смежные |
| `declensions-*` | склонения: nom gen dat acc ins pre loc2 |

Строки не удаляем: `status=deprecated` + `replaced_by`. Дампы > 10 МБ, полный ГАР/ФИАС и GeoNames `RU.zip` — вне git.

---

# Источники и лицензии

Репозиторий — **MIT**. Сырьё хранит свои лицензии (`docs/SOURCES.md`).

| Источник | В каноне |
|---|---|
| Wikidata (CC0) | сиды мест, Q-id |
| Указ № 326 / № 522 | структура ФОИВ |
| ISO 3166-2:RU | коды субъектов |
| GeoNames (CC BY 4.0) | идентификаторы, не архив |
| ГКГН, ФИАС/ГАР | указатели, без дампа |
| hflabs (CC BY-SA 4.0) | только `data/raw/` |

ShareAlike и ODbL в `data/curated/` не копируем. Москва `geonames=524901`, Волга `472776`.

---

# Конвейер

```text
check.py  →  sync.py  →  validate.py  →  index.py
```

| Скрипт | Роль |
|---|---|
| `check.py --json` | детекторы источников; коды **0 / 10 / 2** |
| `sync.py --apply` | upsert по id; deprecate без DELETE |
| `validate.py` | frictionless + инварианты канона |
| `index.py` | derived FTS5 → `knowledge/registry.db` |

Ежедневно: дельта или журнал `data/sources/runs/YYYY-MM-DD.json`. Пустой коммит при нулевой дельте запрещён.

---

# Поиск по индексу

После `python scripts/index.py`:

- `MATCH 'Волга'` → гидроним `wd:Q626`
- `MATCH 'МВД'` → `foiv:mvd`

Индекс производный, gitignored. Канон остаётся CSV.

Склонения: `review=gold` не перезаписывать; автобез проверки — только `needs_review`. `ё` живёт в `name_yo`; в `name_ru` — нормализованная форма.

---

# Loopback JSON · 127.0.0.1:8099

`python scripts/serve.py` — stdlib HTTP, только GET, только loopback (DEC-SERVE-001).

| Путь | Назначение |
|---|---|
| `/healthz` | живость и наличие индекса |
| `/v1/search?q=Волга` | поиск по FTS |
| `/v1/records?id=wd:Q626` | запись по стабильному id |

Не публичный API. Не Datasette, не FastAPI. Не-loopback bind без явного флага — отказ. CORS нет.

---

# Docker Compose

Если на хосте нет CPython 3.12 — тот же канон одним ящиком:

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
docker compose up --build
```

- Python 3.12, `validate → index → serve`
- публикация **`127.0.0.1:8099:8099`**
- `cap_drop: ALL`, read-only, пользователь `10001`

Compose публикует только `127.0.0.1:8099`.

На хосте без Docker: `python scripts/validate.py && python scripts/index.py && python scripts/serve.py`.

---

# Границы

- Нет улиц, муниципалитетов, полного ГАР и `RU.zip`
- Нет LAN/публичного bind, TLS, HTML UI, OpenAPI
- Нет записи в канон через HTTP
- Канон не переписывается целиком: патч по stable id

Локальный прибор, не витрина открытых данных.

---

# Старт

**Хост**

```bash
git clone https://github.com/unhexx/toponym.git
cd toponym
pip install -e ".[dev]"
python scripts/validate.py
python scripts/index.py
python scripts/serve.py
```

**Ящик:** `docker compose up --build`

Проверка: http://127.0.0.1:8099/v1/search?q=Волга

Цитирование: `CITATION.cff`, версия `2026.09.11`.
