"""The IdP image installs its third-party packages from this package's
uv.lock, with hashes, and resolves nothing at build time."""

from __future__ import annotations

import re
from pathlib import Path

import tomllib

PACKAGE = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", re.MULTILINE)


def _pins(path: Path) -> dict[str, str]:
    return {name.lower(): version for name, version in PIN.findall(path.read_text())}


def _locked() -> dict[str, str]:
    lock = tomllib.loads((PACKAGE / "uv.lock").read_text())
    return {
        p["name"].lower(): p["version"]
        for p in lock["package"]
        if "registry" in p.get("source", {})
    }


def _requirement_blocks(path: Path) -> list[str]:
    text = re.sub(r"\\\n\s*", " ", path.read_text())
    return [
        line for line in text.splitlines() if "==" in line and not line.startswith("#")
    ]


def test_idp_image_keeps_its_packages_to_the_lock() -> None:
    pins = _pins(PACKAGE / "requirements.txt")
    locked = _locked()
    assert {"authlib", "cryptography", "starlette"} <= set(pins)
    assert {name: locked.get(name) for name in pins} == pins


def test_idp_image_keeps_every_package_hashed() -> None:
    for name in ("requirements.txt", "build-requirements.txt"):
        for line in _requirement_blocks(PACKAGE / name):
            assert "--hash=sha256:" in line, line


def test_idp_image_keeps_build_time_resolution_off() -> None:
    dockerfile = (PACKAGE / "Dockerfile").read_text()
    runs = re.sub(r"\\\n\s*", " ", dockerfile)
    installs = [line for line in runs.splitlines() if "pip install" in line]
    assert installs, dockerfile
    for line in installs:
        for command in line.split("&&"):
            if "pip install" not in command:
                continue
            # Either every package from a hashed file, or local copies with no
            # dependency and no build environment fetched.
            assert "--require-hashes" in command or (
                "--no-deps" in command and "--no-build-isolation" in command
            ), command
