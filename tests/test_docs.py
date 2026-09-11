from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "design" / "2026-09-09-v1-local-registries.md"

# Living snapshot must not describe the P5-era tree as current.
STALE_SNAPSHOT_PHRASES = (
    "**Next cycle is P6-INDEX.**",
    "Remaining v1 work is P6 FTS",
    "**Empty on every curated row**",
    "**No** `index.py` yet.",
    "`docs/SOURCES.md` | **Missing.**",
    "P6 PENDING",
    "P6-INDEX  (**next**)",
    "Live `geonames` cells are empty",
    "every `geonames` cell empty",
)


def test_design_snapshot_is_released_v1() -> None:
    text = DESIGN.read_text(encoding="utf-8")
    for phrase in STALE_SNAPSHOT_PHRASES:
        assert phrase not in text, phrase
    assert "v1 is released" in text
    assert "2026.09.09" in text
    assert "wd:Q649" in text and "524901" in text
    assert "wd:Q626" in text and "472776" in text
    assert "`index.py` present" in text or "scripts/index.py" in text
    assert "DEC-GN-001" in text
    assert "never insert" in text.lower() or "Do not create `gn:`" in text
    assert "DEC-DECL-001" in text
    assert "DEC-DECL-002" in text
    assert "DEC-TAX-001" in text
    assert "DEC-SERVE-002" in text
    assert "DEC-ONT-001" in text
    assert "DEC-AGENTIX-001" in text
    assert "DEC-HFLABS-001" in text
    assert "DEC-GEO-001" in text
    assert "DEC-SEED-001" in text
    assert "municipalities.csv" in text
    assert "hodonyms.csv" in text
    assert "microtoponyms.csv" in text


def test_readme_has_compose_one_shot() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docker compose up --build" in text
    assert "git pull && docker compose up --build" in text
    assert "127.0.0.1:8099" in text
    assert "python scripts/serve.py" in text
    assert "python scripts/fetch_dump.py" in text
    assert "data/declensions/queue.csv" in text
    assert "http://127.0.0.1:8099/healthz" in text
    assert "http://127.0.0.1:8099/v1/search" in text
    assert "bash Agent-Init.sh" in text
    assert "source .venv/bin/activate" in text


def test_readme_has_shields_badges_and_docs_links() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "img.shields.io" in text
    for needle in (
        "license-MIT",
        "CalVer-2026.09.11",
        "github/actions/workflow/status/unhexx/toponym/ci.yml",
        "python-3.12%2B",
        "docker-compose",
        "CHANGELOG.md",
        "docs/USAGE.md",
        "docs/SOURCES.md",
        "docs/presentation/toponym-2026.09.11.md",
        "https://github.com/unhexx/toponym/releases/tag/2026.09.11",
    ):
        assert needle in text, needle


def test_docs_do_not_publish_all_interfaces() -> None:
    for rel in ("README.md", "docs/USAGE.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "0.0.0.0:8099" not in text, rel
        assert "127.0.0.1:8099" in text, rel


def test_usage_guide_covers_search_and_declensions() -> None:
    path = ROOT / "docs" / "USAGE.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for needle in (
        "/healthz",
        "/v1/search",
        "/v1/records",
        "/v1/declensions",
        "127.0.0.1:8099",
        "data/declensions",
        "nom/gen/dat/acc/ins/pre/loc2",
        "knowledge/registry.db",
        "check.py",
        "sync.py",
        "Только GET",
    ):
        assert needle in text, needle
    assert "data/curated" in text
    assert "GET /v1/declensions" in text


def test_changelog_unreleased_mentions_usage_and_min_update() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    before_loop2, _, _ = text.partition("## [2026.09.11] - 2026-09-11")
    assert "## [Unreleased]" in before_loop2
    assert "2026.09.12" in before_loop2
    assert "blocked-until-tomorrow" in before_loop2
    assert "## [2026.09.12]" in before_loop2
    assert "docs/USAGE.md" in before_loop2
    assert "git pull && docker compose up --build" in before_loop2
    assert "municipalities.csv" in before_loop2
    assert "DEC-SEED-001" in before_loop2


def test_cycle_plan_dod_counts_datapackage_resources() -> None:
    text = (ROOT / "CYCLE_PLAN.md").read_text(encoding="utf-8")
    assert "19 resources" in text
    assert "11 resources" not in text
    assert "14 resources" not in text
    package = json.loads((ROOT / "datapackage.json").read_text(encoding="utf-8"))
    assert len(package["resources"]) == 19


def test_ontology_calver_matches_tagged_release() -> None:
    ont = json.loads((ROOT / "ontology" / "ontology.json").read_text(encoding="utf-8"))
    assert ont["project"]["calver"] == "2026.09.11"


def test_ssot_does_not_require_project_context() -> None:
    sys_prompt = (ROOT / "SYSTEM_PROMPT.md").read_text(encoding="utf-8")
    assert "PROJECT_CONTEXT.md" not in sys_prompt
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "2026.09.11" in agents
    assert "#13" in agents
    spec = (ROOT / "TASK_SPECIFICATION.md").read_text(encoding="utf-8")
    assert "2026.09.11" in spec
    assert "A–L" in spec


def test_adr_is_historical_v1_snapshot() -> None:
    text = (ROOT / "LOCAL_REGISTRIES_DESIGN_AND_ROADMAP.md").read_text(encoding="utf-8")
    assert "исторический снимок" in text
    assert "сиды не закоммичены" not in text
    assert "GitHub #13" in text


def test_product_presentation_exists() -> None:
    deck = ROOT / "docs" / "presentation" / "toponym-2026.09.11.md"
    assert deck.is_file()
    text = deck.read_text(encoding="utf-8")
    for needle in (
        "CSV",
        "check.py",
        "sync.py",
        "validate.py",
        "index.py",
        "127.0.0.1:8099",
        "docker compose up --build",
    ):
        assert needle in text, needle
