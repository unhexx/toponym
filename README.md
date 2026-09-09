# Toponym — реестр российских топонимов

Открытый структурированный реестр топонимов Российской Федерации: населённые пункты, субъекты, гидронимы, оронимы, урбанонимы, ведомства и службы, таблицы склонений.

Лицензия репозитория: [MIT](LICENSE). Импортированные сырьё данные хранят лицензии источников — см. [`data/sources/catalog.yaml`](data/sources/catalog.yaml) и [`docs/SOURCES.md`](docs/SOURCES.md).

## Быстрый старт

```
data/
  curated/          # канонические таблицы (UTF-8 CSV)
  declensions/      # склонения: nom gen dat acc ins pre loc2
  raw/              # снимки источников + SOURCE.md (не смешивать с curated)
  sources/          # каталог источников и даты проверок
schema/             # JSON Schema колонок
scripts/            # импорт и валидация
docs/               # методология, таксономия, лицензии
agents/             # промпты ежедневных агентов
```

Канонический формат хранения: **CSV UTF-8, LF, заголовок обязателен**. Идентификаторы стабильны. Крупные дампы (ГАР/ФИАС, GeoNames RU.zip) **не вендорятся** — только скрипты импорта.

## Типы топонимов

См. [`data/curated/types.csv`](data/curated/types.csv) и [`docs/TAXONOMY.md`](docs/TAXONOMY.md).

Основные классы: хоронимы · ойконимы · гидронимы · оронимы · годонимы · урбанонимы · инсулонимы · ведомства.

## Официальные и открытые источники

| Источник | Что даёт | Лицензия |
|---|---|---|
| ГКГН (Росреестр / Роскадастр) | официальные наименования ~800 тыс. объектов | официальные открытые данные |
| ФИАС / ГАР (ФНС) | адресная иерархия | официальные открытые данные |
| GeoNames `RU.zip` | ~260k+ объектов, ежедневный дамп | CC BY 4.0 |
| OSM / OSMNames / streetmangler | улицы, места, иерархия | ODbL 1.0 |
| epogrebnyak/ru-cities | 1117 городов + коды | производные Росстат/Википедия |
| hflabs/region, hflabs/city | регионы и города + ФИАС/ОКТМО | CC BY-SA 4.0 |
| mfursov/russian-cities | склонения городов | Apache-2.0 |
| Указ Президента №326 от 11.05.2024 | структура ФОИВ | официальный текст |
| Wikidata | Q-id, алиасы | CC0 |

## Склонения

Золотые таблицы в `data/declensions/`. Правила — [`docs/DECLENSIONS.md`](docs/DECLENSIONS.md).

Поля: `nom,gen,dat,acc,ins,pre,loc2,gender,number,indeclinable,paradigm,review`.

Автогенерация (pymorphy2 / Natasha) только с `review=true`.

## Автоматизация

- GitHub Actions: [`.github/workflows/daily.yml`](.github/workflows/daily.yml) — механический импорт + валидация.
- Агент: [`agents/DAILY_UPDATE.md`](agents/DAILY_UPDATE.md) — исследование дельты и курация.

## Цитирование

См. [`CITATION.cff`](CITATION.cff).
