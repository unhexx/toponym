# AGENTS.md

Инструкции для агентов, работающих с репозиторием `unhexx/toponym`.

## Непреложно

1. Сначала прочитать `data/sources/catalog.yaml`, `CHANGELOG.md`, `schema/`.
2. Не переписывать CSV целиком. Патчить по stable id.
3. Не удалять строки: `status=deprecated` + `replaced_by`.
4. Не вендорить дампы > 10 МБ и полный ГАР/ФИАС.
5. CC BY-SA и ODbL — только в `data/raw/<source>/`.
6. Склонения без ручной проверки — только с `review=needs_review`.
7. Хранить `ё` в `name_yo`; нормализованная форма — `name_ru` (`ё`→`е` только там).
8. Кодировка файлов: UTF-8, LF, запятая как CSV-delimiter.

## Project Goal

Качественный локальный реестр российских топонимов и ведомств: Frictionless Tabular Data Package в git, источники с лицензиями и детекторами обновлений, скрипты check/sync/validate/index, derived SQLite FTS, онтология Source/Registry/Mapping/Check/Decision.

## Current Status

P0–P7 на `main`: схемы, сиды, маппинги, check/sync/validate/index, онтология. Документация и релиз — P8–P9, см. `TASK_SPECIFICATION.md`, `.agent/PLAN.md`, `.agent/TODO.md`.

## Recommended Stack (do not deviate without an ADR)

- Language / runtime: Python 3.12+ (project `.venv` only)
- Package manager: `uv` preferred, `pip` fallback
- Data: UTF-8 CSV + Frictionless Table Schema + YAML catalog/mappings
- Index: SQLite FTS5 (derived, not vendored dumps)
- Tests: `pytest`
- Lint: `ruff`

## Exact Commands

```bash
bash Agent-Init.sh
source .venv/bin/activate

# after pyproject.toml exists
uv pip install -e ".[dev]"
# or: python -m pip install -e ".[dev]"

ruff check scripts tests
pytest -q

python scripts/check.py --json
python scripts/validate.py
python scripts/index.py
```

Loop bootstrap: `bash Agent-Init.sh` then `source .venv/bin/activate`.
First orchestrator message: [`prompts/short_orchestrator_prompt.md`](prompts/short_orchestrator_prompt.md).
Spec: [`TASK_SPECIFICATION.md`](TASK_SPECIFICATION.md).
Roadmap ADR: [`LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md`](LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md).

## Ежедневный цикл (актуализация реестров)

Исполняемый промпт: [`agents/DAILY_UPDATE.md`](agents/DAILY_UPDATE.md).

Конвейер: `scripts/check.py --json` → при коде 10 `scripts/sync.py --apply` → `validate.py` → `index.py`.
Код 0: только `data/sources/runs/YYYY-MM-DD.json` (и `checked_at`, если сдвинулся). Код 2: без коммита.
Лимит: 15 минут. Пустой коммит запрещён.

## Definition of Done (any feature)

- [ ] Схемы / `datapackage.json` обновлены в единственном источнике правды
- [ ] Тесты на изменение (фикстура или unit); существующий набор зелёный
- [ ] Нет вендора дампов >10 МБ, нет полного ГАР/ФИАС
- [ ] Upsert по stable id; delete запрещён
- [ ] Коммит как человек mid/senior; conventional commit; без упоминания моделей
- [ ] Один логический слайс на цикл

## Boundaries — NEVER

- Коммитить `.env`, токены, ключи, живые персональные данные
- Переписывать CSV целиком или удалять строки
- Вендорить `RU.zip`, ГАР/ФИАС, любой файл >10 МБ
- Класть CC BY-SA / ODbL в `data/curated/`
- Автосклонения без `review=needs_review` в золотые таблицы
- Ломать верхний уровень типов (`toponym`, не «Торопум»)
- Пустой коммит при нулевой дельте
- Копировать дерево `agentic_loop_template` в продукт (только sibling symlink)

## Git

Автор коммитов: как у существующих коммитов репозитория. Сообщения — естественный русский, от лица разработчика. Не упоминать модели, агентов, LLM.

После каждого завершённого цикла INVEST: merge в `main` и `git push origin main`.
