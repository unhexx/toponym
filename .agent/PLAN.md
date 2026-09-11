# .agent/PLAN.md — Living Project Plan

**Initiative:** toponym v1 local registries
**Template Version:** 3.13.0
**Last Update:** 2026-09-11 (loop 2 tagged 2026.09.11)

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
| P8-DOCS README / CHANGELOG / daily | COMPLETE |
| P9-DONE Reviewer + release 2026.09.09 | COMPLETE |
| v1.1 http_dated RU-only vs dump Last-Modified | COMPLETE |
| v1.1 docs-drift design snapshot | COMPLETE |
| P10-SERVE loopback JSON over FTS | COMPLETE |
| P11-BOX compose one-shot | COMPLETE |
| P12-DOCS DEC-SERVE-001 | COMPLETE |
| P13-DONE reviewer | COMPLETE |
| P14-REL tag 2026.09.11 | COMPLETE |
| P15-DOCS docs match 2026.09.11 | COMPLETE |

## Gate

Каждый цикл: Coder → Tester → Reviewer. После DONE слайса — merge в `main` и push.
Параллель только P2∥P6 после P1. Синхроточка после P5.
Не начинать P9, пока P0–P8 зелёные.

Детальный план циклов после `/design`: `CYCLE_PLAN.md` в корне репозитория.
