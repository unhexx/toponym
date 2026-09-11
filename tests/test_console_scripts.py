from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "toponym-serve": "scripts.serve:main",
    "toponym-index": "scripts.index:main",
    "toponym-validate": "scripts.validate:main",
    "toponym-check": "scripts.check:main",
}


def test_pyproject_declares_console_scripts() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" in text
    for name, target in SCRIPTS.items():
        assert f'{name} = "{target}"' in text


def test_entry_points_resolve_to_main() -> None:
    group = entry_points().select(group="console_scripts")
    by_name = {ep.name: ep.value for ep in group}
    for name, target in SCRIPTS.items():
        assert by_name.get(name) == target, (name, by_name.get(name))


def test_toponym_validate_matches_scripts_path() -> None:
    cli = shutil.which("toponym-validate")
    assert cli, "pip install -e . должен поставить toponym-validate на PATH"
    via_cli = subprocess.run(
        [cli],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    via_mod = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert via_cli.returncode == 0, via_cli.stderr
    assert via_mod.returncode == 0, via_mod.stderr
    assert "ok" in via_cli.stdout
    assert via_cli.stdout == via_mod.stdout


def test_toponym_check_help_does_not_crash() -> None:
    cli = shutil.which("toponym-check")
    assert cli
    proc = subprocess.run(
        [cli, "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "json" in proc.stdout.lower() or "--json" in proc.stdout
