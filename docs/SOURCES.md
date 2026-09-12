# Источники

Витрина — [README](../README.md). Оглавление — [docs/README.md](README.md).

SSOT каталога: [`data/sources/catalog.yaml`](../data/sources/catalog.yaml). Здесь — лицензии и что можно класть в git.

Канон `data/curated/` и `data/declensions/` лицензирован MIT вместе с репозиторием. Строки набраны с официальных имён, ISO 3166-2, Wikidata (CC0) и идентификаторов GeoNames — не скопированы из ShareAlike-таблиц.

## Правила

1. Дамп > 10 МБ и полный ГАР/ФИАС / `RU.zip` не вендорятся.
2. CC BY-SA и ODbL — только `data/raw/<source>/` + `SOURCE.md`. Не копировать в `data/curated/`.
3. `vendor: false` в каталоге: детектор смотрит HEAD/курсор/dated-mods, сам дамп не качается.
4. Атрибуция GeoNames (CC BY 4.0): идентификаторы и, если появятся, координаты из mods — с `source_id=geonames-ru` или пометкой в `notes`.
5. Локальный архив — только вне git: `python scripts/fetch_dump.py --source geonames-ru` (ГАР/ГКГН — с `--url`). `--dest` внутри репозитория отвергается.

## Каталог v1

| `id` | Лицензия | Вендор | Роль |
|---|---|---|---|
| `wikidata` | CC0 | нет | сиды мест, Q-id; маппинг `data/mappings/wikidata.yaml`; годонимы — `hodonyms-ru.sparql` + `scripts/seed_hodonyms.py` (не дамп SPARQL в git) |
| `ukase-326` | официальный текст | нет | ФОИВ (указ № 326, ред. № 522) |
| `geonames-ru` | CC-BY-4.0 | нет (`RU.zip` вне git) | id в колонке `geonames`; без insert `gn:{id}` (DEC-GN-001) |
| `gkgn-opendata` | official-open-data | нет | указатель официальных названий |
| `fias-gar` | official-open-data | нет | указатель; полный ГАР запрещён |
| `hflabs-region` | CC-BY-SA-4.0 | нет | указатель; не в curated |
| `hflabs-city` | CC-BY-SA-4.0 | нет | указатель `data/mappings/hflabs-city.yaml`; не в curated |
| `epogrebnyak-ru-cities` | unknown | нет | watchlist, не импорт |
| `mfursov-russian-cities` | Apache-2.0 | нет | watchlist склонений |
| `nickyx3-settlements` | unknown | нет | watchlist |

Указатели: `data/raw/*/SOURCE.md`. Fetch в tmp: [`scripts/fetch_dump.py`](../scripts/fetch_dump.py).

## Совместимость с MIT-каноном

- **CC0 / официальный текст / ISO** — можно типировать имя и код в curated.
- **CC BY 4.0 (GeoNames)** — идентификаторы допустимы с атрибуцией; архив дампа не хранить.
- **CC BY-SA 4.0 (hflabs)** — ShareAlike. Локально стыковать по `iso` / FIAS, не вставлять их `name` в MIT-таблицы.
- **ODbL (OSM / OSMNames)** — производные остаются в `data/raw/`; в v1 в curated нет.

Маппинги: [`data/mappings/`](../data/mappings/). Онтология источников: `SRC-*` в [`ontology/ontology.json`](../ontology/ontology.json).

## Вне канона (DEC-GEO-001)

Население (ряды по годам), полигоны, GeoJSON и PostGIS **не входят** в CSV-канон.
Точки `lat`/`lon` допустимы (Wikidata P625 / GeoNames mods). Контуры и численность
смотреть во внешних источниках, **не** копируя дампы в git:

- население: Росстат; Wikidata P1082
- границы МО / улиц: Росреестр, OSM (ODbL — только вне `data/curated/`)

