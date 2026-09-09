# Ежедневное обновление unhexx/toponym

Лимит: 15 мин. Патч по id. Пустой коммит запрещён.

1. Прочитать README, AGENTS.md, data/sources/catalog.yaml, CHANGELOG, schema.
2. Дельта источников: GeoNames modifications + RU.zip; ГКГН open data Росреестра / kadastr.ru; Указы ФОИВ (№ 326 + позднейшие); Wikidata P17=Q159 за 48ч; GitHub watchlist (ru-cities, russia_settlements, mfursov, arbaev, streetmangler, hflabs, OSMNames).
3. Insert/update только по stable id (fias/geonames/wikidata/iso/abbr). Delete запрещён — status=deprecated.
4. Склонения: золото вручную для субъекта/города>100k/ФОИВ/крупного гидронима; иначе queue + review=true. Не верить pymorphy для -ово, -ский, X-на-Y, аббревиатур.
5. Лицензии: ODbL и CC BY-SA только в data/raw/. Не вендорить дампы >10 МБ и ГАР.
6. Коммит: chore(data): daily refresh YYYY-MM-DD (N records, sources: …) + CHANGELOG Unreleased.
7. Отчёт: источники / N изменений / SHA или no-op.
