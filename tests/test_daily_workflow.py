from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from scripts.lib.catalog import load_catalog, stamp_catalog_checked_at

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / ".github" / "workflows" / "daily.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
JOURNAL_SCRIPT = ROOT / ".github" / "scripts" / "write_run_journal.py"
FIXTURE_CATALOG = ROOT / "tests" / "fixtures" / "catalog_valid.yaml"


def _load_journal_mod():
    spec = importlib.util.spec_from_file_location("write_run_journal", JOURNAL_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_daily_installs_product_without_agent_init() -> None:
    text = DAILY.read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in text
    assert "Agent-Init.sh" not in text
    assert "agentic_loop_template" not in text
    ci = CI.read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in ci


def test_daily_has_no_missing_check_py_skip() -> None:
    text = DAILY.read_text(encoding="utf-8")
    assert "scripts/check.py отсутствует" not in text
    assert "scripts/check.py missing" not in text
    assert "check_exit=missing" not in text
    assert "python scripts/check.py --json" in text
    assert "python scripts/sync.py --apply" in text
    assert "python scripts/validate.py" in text


def test_daily_always_writes_journal_and_stamps_catalog() -> None:
    text = DAILY.read_text(encoding="utf-8")
    assert "write_run_journal.py" in text
    assert "--check-json /tmp/check.json" in text
    assert "--stamp-catalog" in text
    assert 'if [[ ! -f "data/sources/runs/${TODAY}.json" ]]' not in text
    assert "workflow_dispatch" in text
    assert "empty commit forbidden" in text


def test_stamp_catalog_checked_at_shifts_dates(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(FIXTURE_CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    assert stamp_catalog_checked_at(catalog, "2026-09-11") is True
    payload = load_catalog(catalog)
    assert payload["updated"] == "2026-09-11"
    assert payload["sources"][0]["checked_at"] == "2026-09-11"
    assert stamp_catalog_checked_at(catalog, "2026-09-11") is False


def test_write_run_journal_copies_check_sources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    check_json = tmp_path / "check.json"
    check_json.write_text(
        json.dumps(
            {
                "as_of": "2026-09-11T06:00:00Z",
                "changed_count": 0,
                "error_count": 0,
                "sources": [
                    {
                        "id": "wikidata",
                        "changed": False,
                        "reason": "kind=none",
                        "cursor_old": "",
                        "cursor_new": "",
                        "error": False,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    mod = _load_journal_mod()
    path = mod.write_run_journal(
        today="2026-09-11",
        as_of="2026-09-11T00:00:00Z",
        check_exit=0,
        changed_count=0,
        check_json=check_json,
        runs_dir=tmp_path / "data" / "sources" / "runs",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["check_exit"] == 0
    assert payload["as_of"] == "2026-09-11T06:00:00Z"
    assert payload["sources"][0]["id"] == "wikidata"
    assert payload["changed_count"] == 0
    assert "notes" not in payload
