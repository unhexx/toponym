from __future__ import annotations

import inspect
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import scripts.daily as daily_mod
import scripts.lib.journal as journal_mod
from scripts.daily import changed_source_ids, run_daily
from scripts.lib.catalog import (
    dump_catalog,
    load_catalog,
    patch_catalog_source,
    stamp_catalog_checked_at,
)
from scripts.lib.journal import write_run_journal
from scripts.lib.upsert import UpsertCounts

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / ".github" / "workflows" / "daily.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_CATALOG = ROOT / "tests" / "fixtures" / "catalog_valid.yaml"
FIXTURE_NONE = ROOT / "tests" / "fixtures" / "catalog_none_only.yaml"
NOW = datetime(2026, 9, 12, 6, 0, 0, tzinfo=UTC)


def _journal(root: Path) -> dict:
    path = root / "data" / "sources" / "runs" / "2026-09-12.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _sync_report(*, inserted: int = 0, updated: int = 0, deprecated: int = 0) -> dict:
    counts = UpsertCounts(inserted=inserted, updated=updated, deprecated=deprecated)
    return {"apply": True, **counts.as_dict(), **counts.journal_fields(), "sources": []}


def _patch_pipeline(
    monkeypatch,
    order: list[str],
    *,
    check_report: dict,
    sync_report: dict | None = None,
    validate_code: int = 0,
    index_error: BaseException | None = None,
) -> None:
    def fake_load(_path):
        return {"sources": check_report.get("sources") or []}

    def fake_check(catalog, **_kwargs):
        order.append("check")
        return check_report

    def fake_sync(*, source_id, **_kwargs):
        order.append(f"sync:{source_id}")
        return (sync_report or _sync_report()), 0

    def fake_validate(_dp, **_kwargs):
        order.append("validate")
        return validate_code, []

    def fake_index(_root, _out):
        order.append("index")
        if index_error is not None:
            raise index_error

    def fake_stamp(_path, _today):
        order.append("stamp")
        return True

    def fake_revert(_root):
        order.append("revert")

    monkeypatch.setattr(daily_mod, "load_catalog", fake_load)
    monkeypatch.setattr(daily_mod, "check_catalog", fake_check)
    monkeypatch.setattr(daily_mod, "run_sync", fake_sync)
    monkeypatch.setattr(daily_mod, "validate_tree", fake_validate)
    monkeypatch.setattr(daily_mod, "rebuild_index", fake_index)
    monkeypatch.setattr(daily_mod, "stamp_catalog_checked_at", fake_stamp)
    monkeypatch.setattr(daily_mod, "revert_data", fake_revert)


def test_daily_yml_is_install_run_commit() -> None:
    text = DAILY.read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in text
    assert "python scripts/daily.py" in text
    assert "empty commit forbidden" in text
    assert "workflow_dispatch" in text
    assert 'cron: "0 6 * * *"' in text
    assert "write_run_journal.py" not in text
    assert "scripts/check.py" not in text
    assert "scripts/sync.py" not in text
    assert "scripts/validate.py" not in text
    assert "scripts/index.py" not in text
    ci = CI.read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in ci


def test_changed_source_ids_changed_and_not_error() -> None:
    report = {
        "sources": [
            {"id": "geonames-ru", "changed": True, "error": False, "blocking": True},
            {"id": "fias-gar", "changed": False, "error": True, "blocking": False},
            {"id": "gkgn-opendata", "changed": True, "error": True, "blocking": True},
            {"id": "ukase-326", "changed": True, "error": True, "blocking": False},
            {"id": "", "changed": True, "error": False},
            {"changed": True, "error": False, "id": "wikidata"},
        ]
    }
    assert changed_source_ids(report) == ["geonames-ru", "wikidata"]


def test_run_daily_has_no_injectables() -> None:
    params = inspect.signature(run_daily).parameters
    for name in ("check_fn", "sync_fn", "validate_fn", "index_fn", "stamp_fn", "revert_fn"):
        assert name not in params


def test_catalog_module_has_no_regex_patch() -> None:
    text = (ROOT / "scripts" / "lib" / "catalog.py").read_text(encoding="utf-8")
    assert "import re\n" not in text
    assert "re.compile" not in text
    assert "re.sub" not in text


def test_patch_catalog_source_yaml_roundtrip(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.yaml"
    dump_catalog(
        catalog,
        {
            "updated": "2026-09-01",
            "sources": [
                {
                    "id": "fias-gar",
                    "license": "official-open-data",
                    "vendor": False,
                    "blocking": False,
                    "checked_at": "2026-09-01",
                    "detector": {"kind": "http_head"},
                }
            ],
            "watchlist_github": [],
        },
    )
    assert patch_catalog_source(catalog, "fias-gar", checked_at="2026-09-12", cursor='W/"etag"')
    payload = load_catalog(catalog)
    assert payload["sources"][0]["checked_at"] == "2026-09-12"
    assert payload["sources"][0]["cursor"] == 'W/"etag"'
    assert payload["sources"][0]["blocking"] is False
    raw = catalog.read_text(encoding="utf-8")
    assert "blocking: false" in raw
    assert "W/" in raw


def test_stamp_catalog_checked_at_shifts_dates(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(FIXTURE_CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    assert stamp_catalog_checked_at(catalog, "2026-09-11") is True
    payload = load_catalog(catalog)
    assert payload["updated"] == "2026-09-11"
    assert payload["sources"][0]["checked_at"] == "2026-09-11"
    assert stamp_catalog_checked_at(catalog, "2026-09-11") is False


def test_journal_module_is_dump_only() -> None:
    text = Path(journal_mod.__file__).read_text(encoding="utf-8")
    assert "stamp_catalog" not in text
    assert "stamp-catalog" not in text
    assert "patch_catalog_source" not in text
    assert "scripts.lib.catalog" not in text
    assert "argparse" not in text
    assert "def main" not in text
    assert "journal_counts_from_sync_files" not in text
    assert "sync_json" not in text
    assert "inserted" not in text


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
    path = write_run_journal(
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


def test_write_run_journal_does_not_patch_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "data" / "sources" / "catalog.yaml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(FIXTURE_CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    original_catalog = catalog.read_text(encoding="utf-8")
    path = write_run_journal(
        today="2026-09-11",
        as_of="2026-09-11T00:00:00Z",
        check_exit=10,
        check_report={
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
        runs_dir=tmp_path / "data" / "sources" / "runs",
    )
    assert catalog.read_text(encoding="utf-8") == original_catalog
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["changed_count"] == 2
    assert payload["sources"][0]["cursor_new"] == "should-not-be-patched"
    assert payload["records_upserted"] == 0
    assert payload["records_deprecated"] == 0


def test_write_run_journal_from_upsert_counts(tmp_path: Path) -> None:
    total = UpsertCounts()
    for report in (
        _sync_report(inserted=1, updated=4, deprecated=2),
        _sync_report(inserted=2, updated=0, deprecated=1),
    ):
        total.add(
            UpsertCounts(
                inserted=int(report["inserted"]),
                updated=int(report["updated"]),
                deprecated=int(report["deprecated"]),
            )
        )
    fields = total.journal_fields()
    path = write_run_journal(
        today="2026-09-12",
        as_of="2026-09-12T06:00:00Z",
        check_exit=10,
        runs_dir=tmp_path / "data" / "sources" / "runs",
        records_upserted=fields["records_upserted"],
        records_deprecated=fields["records_deprecated"],
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["records_upserted"] == 7
    assert payload["records_deprecated"] == 3
    assert payload["check_exit"] == 10
    assert "inserted" not in payload


def test_daily_noop_stamps_and_journals(tmp_path: Path, monkeypatch) -> None:
    order: list[str] = []
    check_report = {
        "as_of": "2026-09-12T06:00:00Z",
        "changed_count": 0,
        "error_count": 0,
        "sources": [
            {
                "id": "wikidata",
                "changed": False,
                "error": False,
                "blocking": True,
                "reason": "kind=none",
                "cursor_old": "",
                "cursor_new": "",
            }
        ],
    }
    _patch_pipeline(monkeypatch, order, check_report=check_report)
    summary, code = run_daily(root=tmp_path, now=NOW, offline=True)
    assert code == 0
    assert order == ["check", "stamp"]
    assert summary["check_exit"] == 0
    assert summary["synced"] == []
    assert summary["validate"] == "skip"
    assert summary["stamped"] is True
    assert summary["records_upserted"] == 0
    journal = _journal(tmp_path)
    assert journal["check_exit"] == 0
    assert journal["records_upserted"] == 0
    assert journal["sources"][0]["id"] == "wikidata"


def test_daily_syncs_changed_then_validate_index_journal(tmp_path: Path, monkeypatch) -> None:
    order: list[str] = []
    check_report = {
        "as_of": "2026-09-12T06:00:00Z",
        "changed_count": 2,
        "error_count": 1,
        "sources": [
            {
                "id": "geonames-ru",
                "changed": True,
                "error": False,
                "blocking": True,
                "cursor_new": "2026-09-11",
            },
            {
                "id": "fias-gar",
                "changed": False,
                "error": True,
                "blocking": False,
            },
            {
                "id": "gkgn-opendata",
                "changed": True,
                "error": True,
                "blocking": False,
            },
            {
                "id": "ukase-326",
                "changed": False,
                "error": False,
                "blocking": True,
            },
        ],
    }
    _patch_pipeline(
        monkeypatch,
        order,
        check_report=check_report,
        sync_report=_sync_report(updated=4, deprecated=1),
    )
    summary, code = run_daily(root=tmp_path, now=NOW)
    assert code == 0
    assert order == ["check", "sync:geonames-ru", "validate", "index"]
    assert summary["synced"] == ["geonames-ru"]
    assert summary["validate"] == "0"
    assert summary["stamped"] is False
    assert summary["records_upserted"] == 4
    assert summary["records_deprecated"] == 1
    journal = _journal(tmp_path)
    assert journal["check_exit"] == 10
    assert journal["records_upserted"] == 4
    assert journal["records_deprecated"] == 1


def test_daily_check_exit_2_skips_sync_writes_journal(tmp_path: Path, monkeypatch) -> None:
    order: list[str] = []
    check_report = {
        "as_of": "2026-09-12T06:00:00Z",
        "changed_count": 0,
        "error_count": 1,
        "sources": [
            {
                "id": "geonames-ru",
                "changed": False,
                "error": True,
                "blocking": True,
                "reason": "timeout",
            }
        ],
    }
    _patch_pipeline(monkeypatch, order, check_report=check_report)
    summary, code = run_daily(root=tmp_path, now=NOW)
    assert code == 0
    assert order == ["check"]
    assert summary["check_exit"] == 2
    assert summary["stamped"] is False
    journal = _journal(tmp_path)
    assert journal["check_exit"] == 2
    assert journal["error_count"] == 1


def test_daily_index_fail_keeps_csv_and_journals_counts(tmp_path: Path, monkeypatch) -> None:
    order: list[str] = []
    check_report = {
        "as_of": "2026-09-12T06:00:00Z",
        "changed_count": 1,
        "error_count": 0,
        "sources": [
            {"id": "geonames-ru", "changed": True, "error": False, "blocking": True}
        ],
    }
    _patch_pipeline(
        monkeypatch,
        order,
        check_report=check_report,
        sync_report=_sync_report(inserted=2, updated=3, deprecated=1),
        index_error=sqlite3.Error("disk"),
    )
    summary, code = run_daily(root=tmp_path, now=NOW)
    assert code == 0
    assert order == ["check", "sync:geonames-ru", "validate", "index"]
    assert summary["validate"] == "0"
    assert summary["stamped"] is False
    assert summary["records_upserted"] == 5
    assert summary["records_deprecated"] == 1
    journal = _journal(tmp_path)
    assert journal["check_exit"] == 10
    assert journal["records_upserted"] == 5
    assert journal["records_deprecated"] == 1


def test_daily_validate_fail_reverts_without_journal(tmp_path: Path, monkeypatch) -> None:
    order: list[str] = []
    check_report = {
        "as_of": "2026-09-12T06:00:00Z",
        "changed_count": 1,
        "error_count": 0,
        "sources": [
            {"id": "geonames-ru", "changed": True, "error": False, "blocking": True}
        ],
    }
    _patch_pipeline(
        monkeypatch,
        order,
        check_report=check_report,
        sync_report=_sync_report(inserted=2),
        validate_code=1,
    )
    summary, code = run_daily(root=tmp_path, now=NOW)
    assert code == 1
    assert order == ["check", "sync:geonames-ru", "validate", "revert"]
    assert summary["validate"] == "fail"
    assert summary["journal"] is None
    assert not (tmp_path / "data/sources/runs/2026-09-12.json").exists()


def test_daily_offline_none_only_fixture_stamps(tmp_path: Path) -> None:
    catalog = tmp_path / "data" / "sources" / "catalog.yaml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(FIXTURE_NONE.read_text(encoding="utf-8"), encoding="utf-8")
    summary, code = run_daily(root=tmp_path, now=NOW, offline=True, session=None)
    assert code == 0
    assert summary["check_exit"] == 0
    assert summary["stamped"] is True
    payload = load_catalog(catalog)
    assert payload["updated"] == "2026-09-12"
    assert payload["sources"][0]["checked_at"] == "2026-09-12"
    journal = _journal(tmp_path)
    assert journal["check_exit"] == 0
    assert journal["sources"][0]["id"] == "wikidata"
    assert journal["records_upserted"] == 0
