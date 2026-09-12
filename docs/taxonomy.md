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

Малые сиды (DEC-SEED-001, не дамп ГАР): `data/curated/municipalities.csv`, `hodonyms.csv`, `microtoponyms.csv` — десятки строк Wikidata CC0, не полный реестр улиц/МО.

Дромонимы / сёла / площади (DEC-SEED-002): `data/curated/dromonyms.csv`, `villages.csv`, `agoronyms.csv`. Улица ≠ площадь.

Полная таблица типов: `data/curated/types.csv`.
