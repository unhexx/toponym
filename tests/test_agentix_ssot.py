from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "agentic_loop_template"
SIBLING = (ROOT.parent / "agentic_loop_template").resolve()


def test_agentix_not_tracked_in_git() -> None:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    paths = [item.decode("utf-8") for item in raw.split(b"\0") if item]
    vendored = [
        rel
        for rel in paths
        if rel == "agentic_loop_template" or rel.startswith("agentic_loop_template/")
    ]
    assert not vendored, vendored


def test_gitignore_and_dockerignore_exclude_template() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for text in (gitignore, dockerignore):
        assert "agentic_loop_template" in text
        assert "agentic_loop_template/" in text


def test_agent_init_prefers_sibling_symlink() -> None:
    text = (ROOT / "Agent-Init.sh").read_text(encoding="utf-8")
    assert "../agentic_loop_template" in text
    assert "ln -s" in text
    sibling_at = text.find("$ROOT/../agentic_loop_template")
    nested_at = text.find("$ROOT/agentic_loop_template/memory")
    assert sibling_at != -1
    assert nested_at == -1 or sibling_at < nested_at


def test_agent_init_falls_back_without_template() -> None:
    text = (ROOT / "Agent-Init.sh").read_text(encoding="utf-8")
    assert "PRODUCT_ONLY" in text
    assert 'pip install -e ".[dev]"' in text
    assert "Продуктовый путь" in text
    detect = text.split("if [[ ! -d .venv ]]")[0]
    assert "exit 1" not in detect
    assert "product-only" in text
    proc = subprocess.run(
        ["bash", "-n", str(ROOT / "Agent-Init.sh")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_local_template_is_symlink_to_sibling() -> None:
    if not TEMPLATE.exists() and not TEMPLATE.is_symlink():
        return
    assert TEMPLATE.is_symlink(), "DEC-AGENTIX-001: дерево шаблона не копировать"
    target = TEMPLATE.resolve()
    assert target.name == "agentic_loop_template"
    assert SIBLING.exists()
    assert target == SIBLING


def test_dec_agentix_001_accepted() -> None:
    payload = json.loads((ROOT / "ontology" / "ontology.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in payload["entities"]}
    row = by_id["DEC-AGENTIX-001"]
    assert row["type"] == "Decision"
    assert row["status"] == "accepted"
    assert "symlink" in row["summary"].casefold()
