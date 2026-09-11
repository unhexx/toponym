# ФИАС / ГАР

- URL: https://fias.nalog.ru/
- Лицензия: official-open-data
- Каталог: `fias-gar`

Полный ГАР/ФИАС **не вендорить**. Это указатель; поле `fias` в каноне может быть пустым. GUID при необходимости снимать из официальной выгрузки **вне дерева репозитория**.

Прямого URL архива в каталоге нет. Если есть конкретная ссылка, скачать только в tmp:

```bash
python scripts/fetch_dump.py --source fias-gar --url URL --dest /tmp/toponym-gar
python scripts/fetch_dump.py --source fias-gar --dry-run
```

Без `--url` скрипт не качает (портал, не файл). `--dest` внутри git отвергается. Дамп не коммитить.
