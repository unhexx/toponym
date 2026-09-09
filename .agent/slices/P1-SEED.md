# P1-SEED — бриф для локального агента

**Ветка:** `feature/P1-seed` → `main`  
**Зависит от:** P0 (уже в `main`)  
**Параллель:** нет — следующий слайс после merge P1: P2 и P6 можно параллелить

## Цель
Заполнить канонические сиды: ФО, 89 субъектов, крупные города, гидронимы/оронимы, ФОИВ и прочие органы, золотые склонения. Починить `types` (верхний тип `toponym`, oikonym цел).

## Файлы (datapackage resources)
- `data/curated/types.csv` (есть — проверить/починить)
- `data/curated/federal-districts.csv`
- `data/curated/regions.csv`
- `data/curated/cities-major.csv`
- `data/curated/hydronyms-major.csv`
- `data/curated/oronyms-major.csv`
- `data/curated/agencies-foiv.csv`
- `data/curated/agencies-other.csv`
- `data/declensions/regions.csv`
- `data/declensions/cities-major.csv`
- `data/declensions/agencies.csv`

## Правила (AGENTS.md)
- UTF-8, LF, CSV `,`, заголовок обязателен
- stable `id`; не вендорить >10 МБ / ГАР
- `name_yo` с ё; `name_ru` нормализация ё→е
- склонения: золото без автоперезаписи

## Acceptance
- все resources из `datapackage.json` существуют и ≥1 строка
- types.oikonym / верхний `toponym` цел (не «Торопум»)

## Definition of done слайса
Коммиты на русском, без пустого коммита. После апрува: merge `--no-ff` в `main` + push.
