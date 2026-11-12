"""The WSR dashboard API image installs uv.lock's packages, with hashes."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", re.M)


def test_wsr_api_image_keeps_its_packages_to_the_lock() -> None:
    lock = tomllib.loads((HERE / "uv.lock").read_text())
    locked = {
        p["name"].lower(): p["version"]
        for p in lock["package"]
        if "registry" in p.get("source", {})
    }
    requirements = (HERE / "requirements.txt").read_text()
    pins = {name.lower(): version for name, version in PIN.findall(requirements)}
    assert {"fastapi", "uvicorn", "pydantic"} <= set(pins)
    assert {name: locked.get(name) for name in pins} == pins
    flat = re.sub(r"\\\n\s*", " ", requirements)
    assert all(
        "--hash=sha256:" in line
        for line in flat.splitlines()
        if "==" in line and not line.startswith("#")
    )
    dockerfile = (HERE / "Dockerfile").read_text()
    installs = [line for line in dockerfile.splitlines() if "pip install" in line]
    assert installs == ["RUN pip install --no-cache-dir --require-hashes -r requirements.txt"]
    assert "\nUSER " in dockerfile
