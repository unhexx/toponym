# hflabs/city

- URL: https://github.com/hflabs/city
- Лицензия: CC-BY-SA-4.0
- Каталог: `hflabs-city`

CSV городов **не вендорить** и **не копировать** в `data/curated/` (DEC-HFLABS-001). Канонические строки городов типизируются из официальных названий и идентификаторов Wikidata (CC0), не из этой таблицы.

Локальный join: [`data/mappings/hflabs-city.yaml`](../../mappings/hflabs-city.yaml) — по `fias_id` на существующих строках; поле `city` в MIT-канон не переносится.
