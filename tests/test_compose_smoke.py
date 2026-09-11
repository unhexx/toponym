from __future__ import annotations

import json
import shutil
import socket
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "compose.yaml"
BASE = "http://127.0.0.1:8099"


def docker_ok() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        version = subprocess.run(
            ["docker", "compose", "version"],
            check=False,
            capture_output=True,
            timeout=15,
        )
        info = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return version.returncode == 0 and info.returncode == 0


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) != 0


@pytest.mark.compose
@pytest.mark.skipif(not docker_ok(), reason="docker unavailable")
def test_compose_up_search() -> None:
    if not _port_free(8099):
        pytest.skip("8099 in use")
    up = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "up", "--build", "-d", "--wait"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    try:
        if up.returncode != 0:
            pytest.fail(f"compose up failed: {up.stderr or up.stdout}")
        with urllib.request.urlopen(f"{BASE}/healthz", timeout=5) as resp:
            health = json.loads(resp.read().decode())
        assert resp.status == 200
        assert health["ok"] is True
        for query, expected in (("Волга", "wd:Q626"), ("МВД", "foiv:mvd")):
            url = BASE + "/v1/search?" + urllib.parse.urlencode({"q": query})
            with urllib.request.urlopen(url, timeout=5) as resp:
                payload = json.loads(resp.read().decode())
            assert expected in payload["ids"], payload
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE), "down", "-v"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            timeout=60,
        )
