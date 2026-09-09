# .agent/TODO.md — Task Backlog

**Initiative:** toponym v1 local registries
**Status:** P2-MAP complete; next P3-CHECK

## In progress

- [ ] P3-CHECK-01: scripts/check.py + pytest (exit 0 no-op, JSON report)

## Pending

- [ ] P4-SYNC-01: scripts/sync.py upsert/deprecate + pytest fixture 2→3
- [ ] P5-VAL-01: scripts/validate.py + frictionless; broken CSV fails
- [ ] P6-INDEX-01: scripts/index.py SQLite FTS; search Волга / МВД
- [ ] P7-ONT-01: ontology/ontology.json with DEC-REG-001 and Source list
- [ ] P8-DOCS-01: README quick start, CHANGELOG 2026.09.09, DAILY_UPDATE → check.py
- [ ] P9-DONE-01: Reviewer gate, no vendor >10MB, tag/release 2026.09.09

## Done

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
