# .agent/TODO.md — Task Backlog

**Initiative:** toponym v1 local registries
**Status:** Loop 2 P10–P13 COMPLETE on `feature/P10-serve` (DEC-SERVE-001)

## In progress

## Pending

## Done

- [x] P13-DONE-01: reviewer gate (ruff, pytest, validate, compose smoke Волга/МВД); no tag
- [x] P12-DOCS-01: README docker path, ontology DEC-SERVE-001, CHANGELOG
- [x] P11-BOX-01: Dockerfile + compose.yaml + entrypoint + file-contract tests
- [x] P10-SERVE-01: `scripts/serve.py` handle() JSON; bind 127.0.0.1:8099; `fts_search`

- [x] v1.1-DOCS-DRIFT: дизайн v1 = выпущенный контур; geonames Москва `524901`, Волга `472776`
- [x] v1.1-HTTP-DATED: `http_dated` ignores dump Last-Modified; cursor stays mods date
- [x] P9-DONE-01: Reviewer gate, no vendor >10MB, tag/release 2026.09.09
- [x] P8-DOCS-01: README quick start, CHANGELOG honest Unreleased, SOURCES.md, review=gold/needs_review
- [x] P7-ONT-01: ontology/ontology.json with DEC-REG-001 and Source list
- [x] P6-INDEX-01: scripts/index.py SQLite FTS; search Волга / МВД
- [x] P5-VAL-01: scripts/validate.py + frictionless; broken CSV fails
- [x] P4-SYNC-01: scripts/sync.py upsert/deprecate + pytest fixture 2→3
- [x] P3-CHECK-01: scripts/check.py + pytest (exit 0 no-op, JSON report)
- [x] P2-MAP-01: data/mappings/{geonames,gkgn,fias-pointer,hflabs-region,ukase-326}.yaml
- [x] P1-SEED-01: federal-districts.csv, regions.csv, cities-major.csv
- [x] P1-SEED-02: hydronyms-major.csv, oronyms-major.csv
- [x] P1-SEED-03: agencies-foiv.csv, agencies-other.csv
- [x] P1-SEED-04: declensions/{regions,cities-major,agencies}.csv (золото)
- [x] P0-SCH-01: schema + pyproject + catalog detectors + tests/test_schema.py
- [x] P0-LOOP-01: consumer-starter full — Agent-Init.sh, symlink SSOT, gitignore, living plans, prompts
- [x] P0-SPEC-01: TASK_SPECIFICATION.md без плейсхолдеров
- [x] P0-DESIGN-01: CYCLE_PLAN.md + docs/design/2026-09-09-v1-local-registries.md
- [x] P0-DAILY-01: agents/DAILY_UPDATE.md — конвейер check/sync/validate/index + runs-журнал
