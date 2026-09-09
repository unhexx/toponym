# .agent/PLAN.md — Living Project Plan

**Initiative:** toponym v1 local registries
**Template Version:** 3.13.0
**Last Update:** 2026-09-09 (P7-ONT)

## Phase Status

| Phase | Status |
|-------|--------|
| P0-BOOT Agentix + schemas | COMPLETE |
| P1-SEED curated + declensions | COMPLETE |
| P2-MAP source mappings | COMPLETE |
| P3-CHECK scripts/check.py | COMPLETE |
| P4-SYNC scripts/sync.py | COMPLETE |
| P5-VAL scripts/validate.py | COMPLETE |
| P6-INDEX scripts/index.py | COMPLETE |
| P7-ONT ontology.json | COMPLETE |
| P8-DOCS README / CHANGELOG / daily | PENDING |
| P9-DONE Reviewer + release 2026.09.09 | PENDING |

## Gate

Каждый цикл: Coder → Tester → Reviewer. После DONE слайса — merge в `main` и push.
Параллель только P2∥P6 после P1. Синхроточка после P5.
Не начинать P9, пока P0–P8 зелёные.

Детальный план циклов после `/design`: `CYCLE_PLAN.md` в корне репозитория.
