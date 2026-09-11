# Wikidata

- SPARQL: https://query.wikidata.org/
- Лицензия: CC0
- Каталог: `wikidata`

Массовый дамп Wikidata не вендорится. Сиды городов, гидронимов и оронимов используют стабильные Q-id; запрос списка крупных городов — `cities-major.sparql` в этом каталоге. Расширение МО / улиц / микротопонимов — `k-seeds-expand.sparql` (только указатель, без выгрузки).

Маппинг полей: [`data/mappings/wikidata.yaml`](../../mappings/wikidata.yaml) (Q-id → `wd`, P625 → `lat`/`lon`; delete_policy=pointer).
