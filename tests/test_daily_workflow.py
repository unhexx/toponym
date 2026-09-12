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
    ci = CI.read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in ci


def test_daily_has_no_missing_check_py_skip() -> None:
    text = DAILY.read_text(encoding="utf-8")
    assert "scripts/check.py отсутствует" not in text
    assert "scripts/check.py missing" not in text
    assert "check_exit=missing" not in text
    assert "python scripts/check.py --json" in text
    assert 'python scripts/sync.py --source "$src" --apply --check-json /tmp/check.json' in text
    assert "python scripts/sync.py --apply --check-json /tmp/check.json" not in text
    assert "python scripts/validate.py" in text
    assert "refusing sync/commit" not in text
    assert "check.py exit 2; skip sync, write journal" in text


def test_daily_writes_journal_and_stamps_catalog_only_on_noop() -> None:
    text = DAILY.read_text(encoding="utf-8")
    assert "write_run_journal.py" in text
    assert "--check-json /tmp/check.json" in text
    assert "--stamp-catalog" not in text
    assert "--changed-count" not in text
    assert "json.load(open('/tmp/check.json')).get('changed_count')" in text
    assert 'echo "changed_count=1"' not in text
    assert 'if [[ ! -f "data/sources/runs/${TODAY}.json" ]]' not in text
    assert "workflow_dispatch" in text
    assert "empty commit forbidden" in text
    stamp_block = (
        'if [[ "$CHECK_EXIT" -eq 0 ]]; then\n'
        '            python scripts/check.py --stamp --today "$TODAY"\n'
        "          fi\n"
    )
    assert stamp_block in text
    assert text.count("python scripts/check.py --stamp") == 1
    exit2_at = text.index("check.py exit 2; skip sync, write journal")
    stamp_at = text.index("python scripts/check.py --stamp")
    assert stamp_at > exit2_at
    exit2_block = text[text.index('if [[ "$CHECK_EXIT" -eq 2 ]]') : exit2_at]
    assert "--stamp" not in exit2_block


def test_daily_syncs_only_changed_sources() -> None:
    text = DAILY.read_text(encoding="utf-8")
    assert 'python scripts/sync.py --source "$src" --apply --check-json /tmp/check.json' in text
    assert "index.py || true" not in text
    assert "python scripts/index.py" in text
    assert "s.get('changed')" in text
    assert "s.get('error')" in text
    assert "s.get('blocking'" in text
    assert "blocking-error" not in text
    assert "blocking_error" not in text
    assert "--all" not in text
    assert "open('/tmp/check.json', encoding='utf-8')" in text
    sync_lines = [
        line
        for line in text.splitlines()
        if "scripts/sync.py" in line and not line.lstrip().startswith("#")
    ]
    assert sync_lines
    for line in sync_lines:
        assert "--source" in line
        assert "--all" not in line
    sync_block = text[
        text.index('if [[ "$CHECK_EXIT" -eq 10 ]]') : text.index("write_run_journal.py")
    ]
    assert "python scripts/sync.py --source" in sync_block
    assert "for src" in sync_block
    assert "mapfile" in sync_block
    assert "< <(" not in sync_block
    assert "python scripts/index.py" in sync_block
    assert "index.py || true" not in sync_block
    exit2_at = text.index("check.py exit 2; skip sync, write journal")
    journal_at = text.index("write_run_journal.py")
    assert journal_at > exit2_at
    skip_sync = text[text.index('if [[ "$CHECK_EXIT" -eq 2 ]]') : journal_at]
    assert "scripts/sync.py" not in skip_sync


def test_journal_script_is_dump_only() -> None:
    text = JOURNAL_SCRIPT.read_text(encoding="utf-8")
    assert "stamp_catalog" not in text
    assert "stamp-catalog" not in text
    assert "patch_catalog_source" not in text
    assert "scripts.lib.catalog" not in text


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
    catalog = tmp_path / "data" / "sources" / "catalog.yaml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(FIXTURE_CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    original_catalog = catalog.read_text(encoding="utf-8")
    check_json = tmp_path / "check.json"
    check_json.write_text(
        json.dumps(
            {
                "as_of": "2026-09-11T06:00:00Z",
                "changed_count": 2,
                "error_count": 0,
                "sources": [
                    {
                        "id": "wikidata",
                        "changed": False,
                        "reason": "kind=none",
                        "cursor_old": "",
                        "cursor_new": "should-not-be-patched",
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
        changed_count=99,
        check_json=check_json,
        runs_dir=tmp_path / "data" / "sources" / "runs",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["check_exit"] == 0
    assert payload["as_of"] == "2026-09-11T06:00:00Z"
    assert payload["sources"][0]["id"] == "wikidata"
    assert payload["changed_count"] == 2
    assert "notes" not in payload
    assert catalog.read_text(encoding="utf-8") == original_catalog


def test_write_run_journal_main_does_not_patch_catalog(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    catalog = tmp_path / "data" / "sources" / "catalog.yaml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(FIXTURE_CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    original_catalog = catalog.read_text(encoding="utf-8")
    check_json = tmp_path / "check.json"
    check_json.write_text(
        json.dumps(
            {
                "as_of": "2026-09-11T06:00:00Z",
                "changed_count": 2,
                "error_count": 0,
                "sources": [
                    {
                        "id": "example-src",
                        "changed": True,
                        "reason": "etag",
                        "cursor_old": "old",
                        "cursor_new": "should-not-be-patched",
                        "error": False,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    mod = _load_journal_mod()
    mod.main(
        [
            "--today",
            "2026-09-11",
            "--as-of",
            "2026-09-11T00:00:00Z",
            "--check-exit",
            "10",
            "--check-json",
            str(check_json),
        ]
    )
    assert catalog.read_text(encoding="utf-8") == original_catalog
    journal = tmp_path / "data" / "sources" / "runs" / "2026-09-11.json"
    payload = json.loads(journal.read_text(encoding="utf-8"))
    assert payload["changed_count"] == 2
    assert payload["sources"][0]["cursor_new"] == "should-not-be-patched"
