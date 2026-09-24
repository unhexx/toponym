# Wikidata

- SPARQL: https://query.wikidata.org/
- Лицензия: CC0
- Каталог: `wikidata`

Массовый дамп Wikidata не вендорится. Исторический запрос крупных городов (pop≥100k) — `cities-major.sparql`. Harvest городов — `cities-ru.sparql` (P31 Q7930989, не все 1126 городов России). Сёла/пгт — `villages-ru.sparql` (Q15078955 / Q532, без хуторов Q5084; не ГКГН). Площади — `agoronyms-ru.sparql`. Дороги/ЖД — `dromonyms-ru.sparql` (Q34442 / Q728937 ruwiki, не ПП № 928). Гидронимы — `hydronyms-ru.sparql` (озёра Q23397, реки Q4022 ruwiki; не ГКГН). Оронимы — `oronyms-ru.sparql`. Join ФОИВ — `foiv-ru.sparql` (P31 Q4481741/Q4481675/Q14944295, не Q4481793/Q4481792); `python scripts/join_foiv.py` заполняет `wd` на `agencies-foiv.csv`, новые строки не вставляет. Расширение МО / улиц / микротопонимов — `k-seeds-expand.sparql` (только указатель, без выгрузки). JSON/CSV запроса в git не кладётся.

Годонимы: `hodonyms-ru.sparql` (P31 улица Q79007 / бульвар Q54114 / проспект Q628179 / переулок Q1251403 / набережная Q537127, P17=Россия Q159, без площадей Q174782). Выгрузка JSON/CSV в git не кладётся; upsert в `data/curated/hodonyms.csv` — `python scripts/seed_hodonyms.py` по `wd:Q…` (запрос по одному P31). Parent — P131 на курируемый город/субъект или P131* до ISO `RU-*`; без родителя строка пропускается. Это покрытие Wikidata, не ФИАС и не все улицы России.

Муниципалитеты: `municipalities-ru.sparql` (P31 городской округ Q13626398 / муниципальный округ Q3350075 / муниципальный район Q2198484 и Q60849925 / внутригородское МО Q27587207 / городское поселение Q2661988 / сельское поселение Q634099, P17=Россия Q159). Выгрузка JSON/CSV в git не кладётся; upsert в `data/curated/municipalities.csv` — `python scripts/seed_municipalities.py` по `wd:Q…` (запрос по одному P31). Это покрытие Wikidata, не ОКТМО/ГАР и не все МО России.

Микротопонимы: `microtoponyms-ru.sparql` (P31 урочище Q1434274 / Q125505344, овраг Q1361400, поле Q188869, пещера Q35509, парк Q22698, P17=Россия Q159; без леса Q4421 и ущелья Q2042028). Выгрузка JSON/CSV в git не кладётся; upsert в `data/curated/microtoponyms.csv` — `python scripts/seed_microtoponyms.py` по `wd:Q…`. Это покрытие Wikidata, не ГКГН.

Маппинг полей: [`data/mappings/wikidata.yaml`](../../mappings/wikidata.yaml) (Q-id → `wd`, P625 → `lat`/`lon`; delete_policy=pointer).

Known-ids: `python scripts/sync.py --source wikidata --apply` — SPARQL `VALUES` по уже известным Q-id всех seed-таблиц (города, сёла/пгт, гидронимы, оронимы, площади, дороги/ЖД, годонимы, МО, микротопонимы, агентства), fill-if-empty; `inserted=0`, новые Q-id не вставляет. JSON/CSV в git не кладётся. Daily `kind=none` это не зовёт.
