# Таксономия

Витрина — [README](../README.md). Оглавление — [docs/README.md](README.md).

Верхний уровень — справочный список типов (на слайде опечатка «Торопум» → **Toponym / топоним**).

**DEC-TAX-001:** идентификаторы `toponym` (root), `oikonym` и `hydronym` (primary, parent=`toponym`) не переименовывать.

| EN | RU | Что именует |
|---|---|---|
| Toponym | Топоним | любой географический объект |
| Oikonym | Ойконим | город, деревня; EN также place-name / settlement name |
| Hydronym | Гидроним | река, озеро, океан |
| Oronym | Ороним | гора, хребет, холм |
| Urbanonym / Hodonym / Odonym | Урбаноним / годоним | внутригородское; улица = hodonym |
| Dromonym | Дромоним | шоссе, трасса, историческая дорога |
| Microtoponym | Микротопоним | поле, овраг, урочище |

Соседние / подтипы: хороним (ФО, субъект, МО), инсулоним, потамоним, лимноним, агороним, **agency** (ведомства — не топонимы, но в реестре по ТЗ).

Города (DEC-SEED-006): `data/curated/cities-major.csv` — Wikidata P31=Q7930989 (city/town in Russia), P17=Q159; не все 1 126 городов России (ruwiki 13.05.2026) и не полный ОКТМО; без Крыма/новых субъектов. Имя файла `cities-major` историческое.

Муниципалитеты (DEC-SEED-004): `data/curated/municipalities.csv` — МО Wikidata (P31 городской округ / округ / район / поселение / внутригородское, P17=Q159), не полный ОКТМО и не все МО России.

Микротопонимы (DEC-SEED-005): `data/curated/microtoponyms.csv` — Wikidata parks+caves+овраг+урочище+поле (P17=Q159), плюс курируемые extras (леса, бархан, Провал) не как массовые классы; не ГКГН и не все микротопонимы России.

Годонимы (DEC-SEED-003): `data/curated/hodonyms.csv` — улицы Wikidata (P31=Q79007 / Q54114 / Q628179 / Q1251403 / Q537127, P17=Q159), upsert по `wd:Q…`. Покрытие источника, не ФИАС и не все улицы России.

Площади (DEC-SEED-008): `data/curated/agoronyms.csv` — Wikidata P31=Q174782, P17=Q159; не все площади России и не ОМК УМ Москвы. Улица ≠ площадь.

Дромонимы / сёла (DEC-SEED-002): `data/curated/dromonyms.csv`, `villages.csv`. Улица ≠ площадь.

Полная таблица типов: `data/curated/types.csv`.
