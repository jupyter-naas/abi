"""The MCP server image takes no file of settings from its build context and
installs its packages at the versions of naas-abi-core's uv.lock, with hashes."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2]
REPO = CORE.parents[1]
DOCKERFILE = HERE / "Dockerfile.mcp"
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", re.MULTILINE)


def _instructions() -> list[str]:
    text = re.sub(r"\\\n\s*", " ", DOCKERFILE.read_text())
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_mcp_image_keeps_settings_files_out() -> None:
    copies = [line for line in _instructions() if line.startswith(("COPY", "ADD"))]
    assert copies
    assert not any(".env" in line for line in copies)
    # Nor does any image built from the repository root receive one.
    ignored = (REPO / ".dockerignore").read_text().splitlines()
    assert {".env", ".env.*", "**/.env", "**/.env.*"} <= set(ignored)


def test_mcp_image_keeps_its_packages_to_the_core_lock() -> None:
    lock = tomllib.loads((CORE / "uv.lock").read_text())
    locked = {
        p["name"].lower(): p["version"]
        for p in lock["package"]
        if "registry" in p.get("source", {})
    }
    requirements = HERE / "requirements.txt"
    pins = {
        name.lower(): version for name, version in PIN.findall(requirements.read_text())
    }
    assert {"fastmcp", "mcp", "httpx", "python-dotenv"} <= set(pins)
    assert {name: locked.get(name) for name in pins} == pins
    flat = re.sub(r"\\\n\s*", " ", requirements.read_text())
    assert all(
        "--hash=sha256:" in line
        for line in flat.splitlines()
        if "==" in line and not line.startswith("#")
    )


def test_mcp_image_keeps_installs_hashed() -> None:
    installs = [line for line in _instructions() if "pip install" in line]
    assert installs == [
        "RUN pip install --no-cache-dir --require-hashes -r requirements.txt"
    ]
