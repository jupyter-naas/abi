"""Each application image installs its third-party packages from this
package's uv.lock, with hashes, and resolves nothing at build time."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", re.MULTILINE)


def _extras() -> dict[str, list[str]]:
    pyproject = tomllib.loads((PACKAGE / "pyproject.toml").read_text())
    extras = pyproject["project"]["optional-dependencies"]
    return {name: deps for name, deps in extras.items() if name != "all"}


def _apps() -> list[str]:
    return sorted(name.replace("-", "_") for name in _extras())


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


def test_every_app_image_keeps_its_packages_to_the_lock() -> None:
    locked = _locked()
    for extra, deps in _extras().items():
        path = PACKAGE / "requirements" / f"{extra.replace('-', '_')}.txt"
        pins = {n.lower(): v for n, v in PIN.findall(path.read_text())}
        declared = {
            re.split(r"[\[<>=!~ ;]", dep, maxsplit=1)[0].lower().replace("_", "-")
            for dep in deps
            if not dep.startswith("naas-abi-marketplace-modules")
        }
        assert declared <= set(pins), (extra, declared - set(pins))
        assert {name: locked.get(name) for name in pins} == pins, extra


def test_every_app_image_keeps_every_package_hashed() -> None:
    files = [PACKAGE / "build-requirements.txt"]
    files += [PACKAGE / "requirements" / f"{app}.txt" for app in _apps()]
    for path in files:
        blocks = _requirement_blocks(path)
        assert blocks, path
        for line in blocks:
            assert "--hash=sha256:" in line, (path.name, line)


def test_app_images_keep_build_time_resolution_off() -> None:
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
