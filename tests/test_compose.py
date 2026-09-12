from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_SERVICES = {
    "searxng",
    "ollama",
    "local-deep-research",
}


def test_compose_contract() -> None:
    path = ROOT / "compose.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["name"] == "toponym"
    services = data["services"]
    assert list(services) == ["toponym"]
    svc = services["toponym"]
    assert svc["ports"] == ["127.0.0.1:8099:8099"]
    assert "ALL" in svc["cap_drop"]
    assert "no-new-privileges:true" in svc["security_opt"]
    assert svc["read_only"] is True
    assert svc["user"] == "10001:10001"
    assert svc["image"] == "ghcr.io/unhexx/toponym:2026.09.12"
    assert svc["build"] == {"context": ".", "dockerfile": "Dockerfile"}
    assert not (FORBIDDEN_SERVICES & set(services))


def test_compose_ports_are_loopback_only() -> None:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "127.0.0.1:8099:8099" in text
    assert "0.0.0.0:8099" not in text
    ports_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ports:"):
            ports_block = True
            continue
        if ports_block:
            if stripped.startswith("-"):
                assert "127.0.0.1:8099:8099" in stripped
                assert ":8080" not in stripped
                assert ":8100" not in stripped
                assert ":8110" not in stripped
                assert ":8112" not in stripped
            elif stripped and not stripped.startswith("#"):
                ports_block = False


def test_compose_host_publish_never_all_interfaces() -> None:
    data = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    svc = data["services"]["toponym"]
    assert svc.get("network_mode") != "host"
    for port in svc["ports"]:
        mapping = str(port)
        assert mapping.startswith("127.0.0.1:")
        assert not mapping.startswith("0.0.0.0:")


def test_dockerfile_python_312() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.12-slim" in text
    assert ".[dev]" not in text
    assert "searxng" not in text.casefold()
    assert "ollama" not in text.casefold()
    assert "org.opencontainers.image.source" in text
    assert "https://github.com/unhexx/toponym" in text


def test_dockerignore_excludes_venv() -> None:
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".venv" in text


def test_entrypoint_sequence() -> None:
    text = (ROOT / "scripts" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "scripts/validate.py" in text
    assert "scripts/index.py" in text
    assert "scripts/serve.py" in text
    assert text.index("validate.py") < text.index("index.py") < text.index("serve.py")
    assert "check.py" not in text
    assert "sync.py" not in text
    assert "fetch_dump.py" not in text


def test_ci_compose_job_separate_from_unit() -> None:
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    jobs = ci["jobs"]
    assert "test" in jobs
    assert "compose" in jobs
    test_job = jobs["test"]
    compose_job = jobs["compose"]
    assert test_job["timeout-minutes"] == 15
    assert compose_job["timeout-minutes"] == 20
    test_text = "\n".join(
        str(step.get("run") or "") for step in test_job["steps"]
    )
    compose_text = "\n".join(
        str(step.get("run") or "") for step in compose_job["steps"]
    )
    assert '-m "not compose"' in test_text
    assert "docker compose" not in test_text
    assert "docker compose up --build" in compose_text
    assert "--wait" in compose_text
    assert "127.0.0.1:8099/healthz" in compose_text
    assert "Волга" in compose_text
    assert "МВД" in compose_text
    assert "wd:Q626" in compose_text
    assert "foiv:mvd" in compose_text
    assert ":8080" not in compose_text
    assert ":8100" not in compose_text
    assert ":8110" not in compose_text
    assert "pip install" not in compose_text


def test_ci_publishes_ghcr_calver_on_main() -> None:
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    jobs = ci["jobs"]
    assert "publish" in jobs
    pub = jobs["publish"]
    assert pub["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert pub["needs"] == ["test", "compose"]
    assert pub["permissions"]["packages"] == "write"
    assert pub["permissions"]["contents"] == "read"
    pub_text = "\n".join(str(step.get("run") or "") for step in pub["steps"])
    assert "ghcr.io/unhexx/toponym" in pub_text
    assert "${IMAGE}:${VERSION}" in pub_text
    assert "${IMAGE}:CalVer" in pub_text
    assert "docker push" in pub_text
    assert "docker login ghcr.io" in pub_text
    assert "visibility=public" in pub_text
    assert "searxng" not in pub_text.casefold()
    assert "ollama" not in pub_text.casefold()
    assert ":8080" not in pub_text
    assert ":8100" not in pub_text
    assert ":8110" not in pub_text
