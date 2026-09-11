# ГКГН (открытые данные Росреестра)

- URL: https://rosreestr.gov.ru/opendata/7706560536svedeniyaizgosudarstvennogokatalogageograficheskikhnazvaniy/
- Лицензия: official-open-data
- Каталог: `gkgn-opendata`

Выгрузки каталога географических названий **не класть в git**, если размер превышает 10 МБ. Канон ссылается идентификаторами, не копией дампа.

Страница каталога — указатель, не файл. Опционально скачать архив вне репозитория:

```bash
python scripts/fetch_dump.py --source gkgn-opendata --url URL --dest /tmp/toponym-gkgn
python scripts/fetch_dump.py --source gkgn-opendata --dry-run
```

Без `--url` скрипт не качает. `--dest` внутри git отвергается. Size gate `data/` и tracked-файлов остаётся.
