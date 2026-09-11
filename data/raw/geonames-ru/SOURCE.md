# GeoNames RU

- Дамп: https://download.geonames.org/export/dump/RU.zip
- Суточные дельты: https://download.geonames.org/export/dump/modifications-{date}.txt и `deletes-{date}.txt`
- Лицензия: CC-BY-4.0
- Каталог: `geonames-ru`

`RU.zip` (десятки МБ) **не хранить в git** и **не класть в `data/`**. В v1 координаты сидов оставляем пустыми, если нет проверенного Wikidata P625 (CC0).

Опционально скачать вне репозитория (`--dest` внутри git отвергается):

```bash
python scripts/fetch_dump.py --source geonames-ru
python scripts/fetch_dump.py --source geonames-ru --dest /tmp/toponym-dumps --dry-run
```

Пишет `$TOPONYM_DUMP_DIR` или `mkdtemp` (`/tmp/toponym-dump-*/RU.zip`). `scripts/sync.py` качает только суточные mods/deletes, не архив.
