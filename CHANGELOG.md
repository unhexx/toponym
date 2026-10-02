# Changelog

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: Calendar Versioning `YYYY.MM.DD`.

## [Unreleased]

### Changed
- Daily 2026-10-02: GeoNames mods обновил координаты села Крым (`wd:Q4242873`, GeoNames `540259`) — upsert 1, deprecate 0. Курсор `geonames-ru` → `2026-10-01`.
- Known-ids Wikidata заполнил пустые `lat`/`lon` у 161 уже существующих строк (`inserted=0`): все 89 субъектов и 8 федеральных округов, 12 ФОИВ, а также отдельные города, сёла, улицы, гидронимы, оронимы, муниципалитеты и один микротопоним. У Санкт-Петербурга появился GeoNames `498817`. Новых Q-id нет. Это не Росстат и не ГКГН.
