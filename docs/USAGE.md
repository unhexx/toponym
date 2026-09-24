# Как пользоваться реестром Toponym

Витрина и пятиминутный старт — в [корневом README](../README.md). Оглавление — [docs/README.md](README.md).

Инструкция для того, кто **уже развернул** актуальную версию из этого репозитория
(`docker compose up --build`, `python scripts/serve.py` или `toponym-serve`) и ищет топонимы и склонения.
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
# то же после pip install: toponym-validate / toponym-index / toponym-serve
```

---

## 2. Что умеет HTTP, чего нет

| Запрос | Что вернёт |
|---|---|
| `GET /healthz` | число записей в индексе |
| `GET /v1/search?q=…` | карточки мест и ведомств |
| `GET /v1/records?id=…` | одна карточка по стабильному id |
| `GET /v1/declensions?id=…` | падежи из CSV (массив hits, ключ `(id, lemma)`) |

В индекс **не входят** `types.csv` и сырьё `data/raw/`. Карточка `records` **не**
дублирует CSV склонений: падежный ряд отдаёт `/v1/declensions`.
`lemma` / `yo` / заполненные падежи из `data/declensions/*.csv` (не `queue.csv`)
попадают в FTS как поисковые алиасы — «Тверской» и «Москвы» находят канон.
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
| `table_name` | нет | `federal-districts`, `regions`, `cities-major`, `hydronyms-major`, `oronyms-major`, `municipalities`, `hodonyms`, `microtoponyms`, `dromonyms`, `villages`, `agoronyms`, `agencies-foiv`, `agencies-other` |
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

## 3.1. Муниципалитеты, улицы, микротопонимы, города

Города (DEC-SEED-006) — реестр Wikidata (CC0): P31=Q7930989 (city/town in Russia), P17=Q159,
upsert по `wd:Q…`. Это не все 1 126 городов России (ruwiki 13.05.2026) и не полный ОКТМО;
без Крыма/новых субъектов. SPARQL JSON в git нет. Имя файла `cities-major` историческое.
Массовая вставка — `python scripts/seed_cities.py` (не `daily.py`).
Муниципалитеты (DEC-SEED-004) — реестр МО Wikidata (CC0): P31 городской округ / муниципальный округ / район /
поселение / внутригородское (Q13626398, Q3350075, Q2198484, Q60849925, Q27587207, Q2661988,
Q634099), P17=Q159, upsert по `wd:Q…`. Это не ОКТМО/ГАР и не все МО России; SPARQL JSON в git нет.
Микротопонимы (DEC-SEED-005) — реестр Wikidata (CC0): P31 урочище / овраг / поле / пещера / парк
(Q1434274, Q125505344, Q1361400, Q188869, Q35509, Q22698), P17=Q159, upsert по `wd:Q…`,
плюс курируемые extras (леса, бархан, Провал) не как массовые классы. Это не ГКГН
и не все микротопонимы России; SPARQL JSON в git нет.
Массовая вставка — `python scripts/seed_municipalities.py` / `seed_microtoponyms.py` (не `daily.py`).
Годонимы (DEC-SEED-003) — реестр улиц Wikidata (CC0): P31 улица/бульвар/проспект/переулок/набережная
(Q79007, Q54114, Q628179, Q1251403, Q537127), P17=Q159, upsert по `wd:Q…`. Это не ФИАС
и не все улицы России; SPARQL JSON в git нет.

| Таблица | Сколько строк | Примеры |
|---|---|---|
| `data/curated/cities-major.csv` | тысячи (Wikidata Q7930989, не Росстат) | Москва, Самара, Тобольск |
| `data/curated/municipalities.csv` | тысячи (Wikidata, не ОКТМО) | городской округ Самара, городской округ город Уфа |
| `data/curated/hodonyms.csv` | тысячи (Wikidata, не ФИАС) | Тверская улица, Арбат, Невский проспект |
| `data/curated/microtoponyms.csv` | сотни (Wikidata, не ГКГН) | Синий камень, Капова пещера, Нескучный сад |

```bash
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Тверская'
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Тверской'
curl -sSG http://127.0.0.1:8099/v1/search \
  --data-urlencode 'q=Самара' \
  --data-urlencode 'table_name=municipalities'
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Синий'
```

«Тверская» бьёт в `name_ru`. «Тверской» — падежный алиас из
`data/declensions/hodonyms.csv` (`review=needs_review`, не pymorphy-золото).
Новые строки склонений — `nom` + `review=needs_review`. Полный ГАР/ФИАС по-прежнему вне git.

---

## 3.2. Дромонимы, сёла, площади

Типы `dromonym` / `village` / `agoronym` уже были в `types.csv` (исторический DEC-SEED-002).

Площади (DEC-SEED-008) — реестр Wikidata (CC0): P31=Q174782, P17=Q159, upsert по `wd:Q…`.
Это не все площади России и не ОМК УМ Москвы. SPARQL JSON в git нет.
Массовая вставка — `python scripts/seed_agoronyms.py` (не `daily.py`).
Красная площадь живёт в `agoronyms.csv`, не в годонимах. Улица ≠ площадь.

Дороги и железные дороги (DEC-SEED-009) — реестр Wikidata (CC0): P31=Q34442 (road)
и P31=Q728937 (railway, ruwiki sitelink), P17=Q159, upsert по `wd:Q…`.
Это не перечень федеральных трасс ПП № 928 и не OSM. SPARQL JSON в git нет.
Массовая вставка — `python scripts/seed_dromonyms.py` (не `daily.py`).
Транссиб / БАМ / М11 сохранены.

Сёла и пгт (DEC-SEED-007) — реестр Wikidata (CC0): P31=Q15078955 (пгт) и P31=Q532
(village), P17=Q159, upsert по `wd:Q…`. Это не ГКГН и не все сельские населённые
пункты России (Росстат). Хутора Q5084 нет. SPARQL JSON в git нет.
Массовая вставка — `python scripts/seed_villages.py` (не `daily.py`).
`type_id=village` и у пгт. Бородино / Вёшенская сохранены.

Гидронимы (DEC-SEED-010) — реестр Wikidata (CC0): P31 озеро Q23397 и река Q4022
с ruwiki sitelink, P17=Q159, upsert по `wd:Q…`. Моря Q165 остаются FILL_IF_EMPTY
и не входят в SPARQL VALUES. Один SELECT; при too_large/timeout входящие реки
отбрасываются, озёра и моря остаются. Это не ГКГН и не все реки России.
SPARQL JSON в git нет. Массовая вставка — `python scripts/seed_hydronyms.py`
(не `daily.py`). Волга и Дон — gold.

Оронимы — массовая вставка `python scripts/seed_oronyms.py` (не `daily.py`):
P31 гора Q8502, хребет Q46831, вулкан Q8072, остров Q23442 и полуостров Q34763,
P17=Q159; остров/полуостров — `type_id=insulonym`. Запрос по одному VALUES-типу.
Это не ГКГН и не все горы России. Эльбрус, Уральские горы и Сахалин сохранены.
Байкал в оронимах не живёт.

| Таблица | Сколько строк | Примеры |
|---|---|---|
| `data/curated/agoronyms.csv` | сотни (Wikidata Q174782, не ОМК УМ) | Красная площадь, Дворцовая площадь |
| `data/curated/dromonyms.csv` | сотни (Wikidata Q34442 / Q728937 ruwiki, не ПП № 928) | Транссибирская магистраль (Транссиб), М11 «Нева» |
| `data/curated/villages.csv` | десятки тысяч (Wikidata Q15078955/Q532, не ГКГН) | Бородино, Вешенская |
| `data/curated/hydronyms-major.csv` | десятки тысяч (Wikidata Q23397 / Q4022 ruwiki, не ГКГН) | Волга, Дон, Байкал |

```bash
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Транссиб'
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Бородино'
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=Красная площадь'
```

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
| `data/declensions/cities-major.csv` | города (Wikidata P31=Q7930989) |
| `data/declensions/hydronyms-major.csv` | гидронимы (Волга, Дон — gold) |
| `data/declensions/oronyms-major.csv` | оронимы |
| `data/declensions/municipalities.csv` | муниципалитеты |
| `data/declensions/hodonyms.csv` | годонимы |
| `data/declensions/microtoponyms.csv` | микротопонимы |
| `data/declensions/dromonyms.csv` | дромонимы |
| `data/declensions/villages.csv` | сёла |
| `data/declensions/agoronyms.csv` | площади |
| `data/declensions/agencies.csv` | ведомства (часто две строки на id: аббревиатура + полное имя) |

Ключ стыковки с поиском — поле **`id`**.

Автоформы в канон не пишутся. Очередь (не ресурс datapackage):

```bash
python scripts/declensions_queue.py --id wd:Q42 --lemma Примерск
# отказ: python scripts/declensions_queue.py --id wd:Q649 --lemma Москва --review gold
```

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
# города Wikidata P31=Q7930989 (не все 1 126 городов России)
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

В `records` падежей нет. FTS-колонка `lemma` — только поисковые алиасы
(лемма/ё/заполненные падежи); полный ряд — CSV или `GET /v1/declensions`.

---

## 6. Что есть в каноне, чего нет

Есть: 8 федеральных округов, 89 субъектов, города Wikidata P31=Q7930989
(не все 1 126 городов России и не Росстат; DEC-SEED-006),
гидронимы Wikidata P31=Q23397 / Q4022 ruwiki (не ГКГН и не все реки России; DEC-SEED-010),
крупные оронимы, ФОИВ и смежные ведомства, золотые склонения к части из них,
реестр муниципалитетов, годонимов и микротопонимов Wikidata (исторический малый сид DEC-SEED-001),
площадей Wikidata P31=Q174782 (не все площади России; DEC-SEED-008),
дорог и ЖД Wikidata P31=Q34442 / Q728937 ruwiki (не перечень федеральных трасс ПП № 928 и не OSM; DEC-SEED-009)
и сёл/пгт Wikidata P31=Q15078955 / Q532 (не ГКГН и не все сельские населённые пункты России; DEC-SEED-007).

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

# Волга → wd:Q626 (склонение в hydronyms-major.csv, type_code=potamonym)
curl -sSG http://127.0.0.1:8099/v1/declensions --data-urlencode 'id=wd:Q626'
grep -h '^wd:Q626,' data/declensions/hydronyms-major.csv

# МВД → foiv:mvd
curl -sSG http://127.0.0.1:8099/v1/search --data-urlencode 'q=МВД'
grep -h '^foiv:mvd,' data/declensions/agencies.csv
```

Проверка «сервис отвечает»: `curl -sS http://127.0.0.1:8099/healthz` → `"ok": true`.
