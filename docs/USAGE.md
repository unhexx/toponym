# Как пользоваться реестром Toponym

Инструкция для того, кто **уже развернул** актуальную версию из этого репозитория
(`docker compose up --build` или `python scripts/serve.py`) и ищет топонимы и склонения.
Сеть наружу **не нужна** для поиска по канону: все имена и падежи лежат в git-CSV.
Сеть нужна только для `check.py` / `sync.py` (есть ли обновление у источников).

Слушает **только этот компьютер**: `http://127.0.0.1:8099`. С соседней машины в LAN
сервис недоступен — так задумано.

---

## 1. Жив ли сервис

```bash
curl -sS http://127.0.0.1:8099/healthz
```

Ожидаемо: `"ok": true` и `"records"` > 0. Если соединение отказ — контейнер/процесс
не запущен. Если `"error": "index_unavailable"` — нет `knowledge/registry.db`
(на хосте: `python scripts/index.py`; в Compose индекс собирается при старте).

Compose:

```bash
docker compose ps
# STATUS должен быть healthy (или Up)
```

Хост без Docker:

```bash
python scripts/validate.py    # канон CSV; сеть не нужна
python scripts/index.py       # пересобрать FTS
python scripts/serve.py       # 127.0.0.1:8099
```

---

## 2. Что умеет HTTP, чего нет

| Запрос | Что вернёт |
|---|---|
| `GET /healthz` | число записей в индексе |
| `GET /v1/search?q=…` | карточки мест и ведомств |
| `GET /v1/records?id=…` | одна карточка по стабильному id |
| `GET /v1/declensions?id=…` | падежи из CSV (массив hits, ключ `(id, lemma)`) |

В индекс **не входят** склонения, `types.csv` и сырьё `data/raw/`.
Падежи **не** кладутся в FTS: `/v1/declensions` читает `data/declensions/*.csv` по `id`.
Только GET; POST/PUT — 405.

Поля карточки: `id`, `table_name`, `type_id`, `name_ru`, `name_yo`, `name_en`,
`abbr`, `parent_id`, `admin1`, `lat`, `lon`, `wd`, `geonames`, `fias`, `oktmo`,
`iso`, `status`, `source_id`. `lat`/`lon` — числа JSON, если заполнены; в FTS
не входят.

Идентификаторы стабильны: `wd:Q649` (Москва), `iso:RU-MOS`, `foiv:mvd`, `fo:cfo`.

---

## 3. Поиск топонима (HTTP)

Запрос — **точная фраза** (не булевый Google). Кодируйте кириллицу.

```bash
# река
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Волга'

# ведомство по аббревиатуре
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=МВД'

# город
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Москва'

# сузить таблицу и число строк
curl -sSG http://127.0.0.1:8099/v1/search \
  --data-urlencode 'q=Дон' \
  --data-urlencode 'table_name=hydronyms-major' \
  --data-urlencode 'limit=5'

# только действующие (не deprecated)
curl -sSG http://127.0.0.1:8099/v1/search \
  --data-urlencode 'q=Москва' \
  --data-urlencode 'status=active'
```

Параметры `/v1/search`:

| Параметр | Обязателен | Значение |
|---|---|---|
| `q` | да | 1–200 символов |
| `limit` | нет | 1–100, по умолчанию 20 |
| `table_name` | нет | `federal-districts`, `regions`, `cities-major`, `hydronyms-major`, `oronyms-major`, `municipalities`, `hodonyms`, `microtoponyms`, `agencies-foiv`, `agencies-other` |
| `status` | нет | `all` (по умолчанию), `active`, `deprecated` |

Ноль совпадений — HTTP 200, `"count": 0`, пустые `ids`/`hits` (не 404).

Карточка по id (двоеточие в id — в query, не в path):

```bash
curl -sSG http://127.0.0.1:8099/v1/records --data-urlencode 'id=wd:Q649'
curl -sSG http://127.0.0.1:8099/v1/records --data-urlencode 'id=foiv:mvd'
curl -sSG http://127.0.0.1:8099/v1/records --data-urlencode 'id=wd:Q626'   # Волга
```

Браузер на той же машине: [http://127.0.0.1:8099/v1/search?q=Волга](http://127.0.0.1:8099/v1/search?q=%D0%92%D0%BE%D0%BB%D0%B3%D0%B0).

`ё`: в `name_ru` хранится нормализация «е»; буква ё — в `name_yo`. Поиск «Орел» и «Орёл» может разойтись; смотрите оба поля в карточке.

---

## 4. Склонения (падежи)

`GET /v1/declensions?id=…` стыкует падежи с карточкой поиска по **`id`**.
Несколько строк на один id (аббревиатура и полное имя ФОИВ) — массив `hits`.
Падежи **не** пишутся в SQLite FTS.

```bash
curl -sSG http://127.0.0.1:8099/v1/declensions --data-urlencode 'id=wd:Q649'
curl -sSG http://127.0.0.1:8099/v1/declensions --data-urlencode 'id=foiv:mvd'
curl -sSG http://127.0.0.1:8099/v1/declensions --data-urlencode 'id=wd:Q626'
```

Офлайн те же CSV (без HTTP). Золото:

| Файл | Что там |
|---|---|
| `data/declensions/regions.csv` | округа и субъекты |
| `data/declensions/cities-major.csv` | крупные города |
| `data/declensions/hydronyms-major.csv` | гидронимы (Волга, Дон — gold) |
| `data/declensions/oronyms-major.csv` | оронимы |
| `data/declensions/municipalities.csv` | муниципалитеты |
| `data/declensions/hodonyms.csv` | годонимы |
| `data/declensions/microtoponyms.csv` | микротопонимы |
| `data/declensions/agencies.csv` | ведомства (часто две строки на id: аббревиатура + полное имя) |

Ключ стыковки с поиском — поле **`id`**.

Колонки: `id,type_code,lemma,yo,gender,paradigm,declinable,nom/gen/dat/acc/ins/pre/loc2,review,source`.

| Падеж | Колонка | Пример (Москва) |
|---|---|---|
| именительный | `nom` | Москва |
| родительный | `gen` | Москвы |
| дательный | `dat` | Москве |
| винительный | `acc` | Москву |
| творительный | `ins` | Москвой |
| предложный | `pre` | Москве |
| второй предложный / местный | `loc2` | (у Дона: *на Дону*) |

`review=gold` — проверено вручную, не перезаписывать. `needs_review` — черновик.

### Найти строку склонения по id из поиска

```bash
# 1) id из HTTP
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Москва' \
  | python -c "import json,sys; print(json.load(sys.stdin)['ids'][0])"
# → wd:Q649

# 2) падежи (без сети)
python - <<'PY'
import csv
from pathlib import Path
want = "wd:Q649"
for path in Path("data/declensions").glob("*.csv"):
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["id"] == want:
                print(path.name, row["lemma"], dict(
                    nom=row["nom"], gen=row["gen"], dat=row["dat"],
                    acc=row["acc"], ins=row["ins"], pre=row["pre"],
                    loc2=row["loc2"], review=row["review"],
                ))
PY
```

Готовый grep (UTF-8):

```bash
grep -h '^wd:Q649,' data/declensions/*.csv
grep -h '^foiv:mvd,' data/declensions/agencies.csv
```

Ключ строки — `(id, lemma)`, не уникальный `id` (DEC-DECL-002).
У МВД две леммы: несклоняемое «МВД» (`paradigm=indecl`) и
«Министерство внутренних дел…» (`agency-head`). Берите нужную.

---

## 5. Полностью без HTTP (офлайн, Excel, DuckDB)

Канон читается как обычный CSV. Сервер не обязателен.

```bash
# все крупные города
# data/curated/cities-major.csv

# субъекты
# data/curated/regions.csv

python - <<'PY'
import csv
from pathlib import Path
q = "волга"
hits = []
for path in Path("data/curated").glob("*.csv"):
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            blob = " ".join(row.get(k) or "" for k in ("name_ru", "name_yo", "name_en", "abbr"))
            if q in blob.casefold():
                hits.append((path.name, row.get("id"), row.get("name_ru"), row.get("abbr")))
for h in hits:
    print(*h, sep="\t")
PY
```

SQLite FTS (после `python scripts/index.py`):

```bash
sqlite3 knowledge/registry.db \
  "SELECT r.id, r.name_ru, r.abbr, r.table_name
   FROM records_fts f JOIN records r ON r.rowid = f.rowid
   WHERE records_fts MATCH '\"Волга\"';"
```

Склонения в `registry.db` **нет**.

---

## 6. Что есть в каноне, чего нет

Есть: 8 федеральных округов, 89 субъектов, крупные города, крупные гидронимы и оронимы,
ФОИВ и смежные ведомства, золотые склонения к части из них,
малые сиды муниципалитетов, годонимов и микротопонимов (DEC-SEED-001).

Нет в этом релизе: полный ГАР/ФИАС, GeoNames `RU.zip`, полный список улиц и МО,
склонения **каждого** ойконима (только золотые/черновые таблицы выше),
публичный Internet/LAN API (host publish не `0.0.0.0`; DEC-SERVE-002),
население / полигоны / GeoJSON / PostGIS (DEC-GEO-001).
Нет строки — нет падежей; не выдумывайте формы из морфоанализатора как канон.

Нормы склонения: [`docs/DECLENSIONS.md`](DECLENSIONS.md). Таксономия типов: [`docs/taxonomy.md`](taxonomy.md).

---

## 7. Сеть наружу

| Действие | Сеть |
|---|---|
| Поиск `/v1/search`, карточка `/v1/records` | нет |
| Чтение CSV / SQLite | нет |
| `python scripts/validate.py` | нет |
| `python scripts/index.py` | нет |
| `python scripts/check.py --json` | да (детекторы источников) |
| `python scripts/sync.py --apply` | да, если источник разрешён к скачиванию |
| Бейджи shields.io в README | да, только картинки README; на работу реестра не влияют |

Офлайн-проверка источников без падения всего контура:

```bash
python scripts/check.py --json --offline
```

Источники с `detector.kind` ≠ `none` в офлайне дадут ошибку — это нормально.

---

## 8. Минимальный сценарий «найти и просклонять»

Нужно: *в городе Москве*, *на берегу Волги*, *в МВД*.

```bash
# Москва → wd:Q649 → gen Москвы, pre Москве
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Москва'
grep -h '^wd:Q649,' data/declensions/cities-major.csv

# Волга → wd:Q626 (строка склонения сейчас в cities-major.csv, type_code=potamonym)
grep -h '^wd:Q626,' data/declensions/*.csv

# МВД → foiv:mvd
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=МВД'
grep -h '^foiv:mvd,' data/declensions/agencies.csv
```

Проверка «сервис отвечает»: `curl -sS http://127.0.0.1:8099/healthz` → `"ok": true`.
