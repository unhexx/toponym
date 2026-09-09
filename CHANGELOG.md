# Changelog

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: Calendar Versioning `YYYY.MM.DD`.

## [Unreleased]

### Added
- Каркас репозитория, таксономия типов, каталог источников.
- Контракт v1: Table Schema, JSON Schema каталога и маппингов, `pyproject.toml`.
- Детекторы обновлений в `data/sources/catalog.yaml`.
- Исполняемый ежедневный промпт `agents/DAILY_UPDATE.md` (check → sync → validate → index; журнал `data/sources/runs/`).
- План циклов `CYCLE_PLAN.md` и дизайн v1.

### Changed
- Каталог источников: обязательные `vendor` и `detector.kind`.

### Note
- Сиды curated-таблиц ещё не в git; появятся в цикле P1.
