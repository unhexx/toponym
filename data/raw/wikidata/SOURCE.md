# Wikidata

- SPARQL: https://query.wikidata.org/
- Лицензия: CC0
- Каталог: `wikidata`

Массовый дамп Wikidata не вендорится. Сиды городов, гидронимов и оронимов используют стабильные Q-id; запрос списка крупных городов — `cities-major.sparql` в этом каталоге. Расширение МО / улиц / микротопонимов — `k-seeds-expand.sparql` (только указатель, без выгрузки).

Годонимы: `hodonyms-ru.sparql` (P31=улица Q79007, P17=Россия Q159, без площадей Q174782). Выгрузка JSON/CSV в git не кладётся; upsert в `data/curated/hodonyms.csv` — `python scripts/seed_hodonyms.py` по `wd:Q…`. Parent — P131 на курируемый город/субъект или P131* до ISO `RU-*`; без родителя строка пропускается. Это покрытие Wikidata, не ФИАС и не все улицы России.

Маппинг полей: [`data/mappings/wikidata.yaml`](../../mappings/wikidata.yaml) (Q-id → `wd`, P625 → `lat`/`lon`; delete_policy=pointer).
