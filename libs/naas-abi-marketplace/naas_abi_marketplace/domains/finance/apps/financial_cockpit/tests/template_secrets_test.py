"""The Financial Cockpit template ships no secret: kickstart generates them,
production refuses the template's values, and Nexus shows no password."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
WEB = APP / "web"
TEMPLATE_VALUES = ("demo", "change-me-to-a-long-random-string")

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def test_template_keeps_its_secrets_empty() -> None:
    values = env_values(WEB / ".env.example")

    assert values["SESSION_SECRET"] == ""
    assert values["ROOT_PASSWORD"] == ""


def kickstart(root: Path) -> dict[str, str]:
    subprocess.run(
        ["node", str(root / "scripts" / "kickstart.mjs"), "--force"],
        check=True,
        capture_output=True,
        text=True,
    )
    return env_values(root / ".env")


@needs_node
def test_kickstart_keeps_secrets_random(tmp_path: Path) -> None:
    root = tmp_path / "web"
    (root / "scripts").mkdir(parents=True)
    (root / "config").mkdir()
    shutil.copy(WEB / "scripts" / "kickstart.mjs", root / "scripts")
    shutil.copy(WEB / ".env.example", root)
    shutil.copy(WEB / "config" / "config.example.yaml", root / "config")

    first, second = kickstart(root), kickstart(root)

    for values in (first, second):
        assert (
            values["ROOT_PASSWORD"] and values["ROOT_PASSWORD"] not in TEMPLATE_VALUES
        )
        assert len(values["SESSION_SECRET"]) >= 32
        assert values["SESSION_SECRET"] not in TEMPLATE_VALUES
    assert first["ROOT_PASSWORD"] != second["ROOT_PASSWORD"]
    assert first["SESSION_SECRET"] != second["SESSION_SECRET"]
    assert (root / ".env").stat().st_mode & 0o077 == 0


def configured(value: str, node_env: str, min_length: int = 1) -> str | None:
    script = (
        "const m = await import(process.argv[1]);"
        "const v = m.configuredSecret(process.argv[2],"
        " {nodeEnv: process.argv[3], minLength: Number(process.argv[4])});"
        "console.log(JSON.stringify(v));"
    )
    out = subprocess.run(
        [
            "node",
            "--no-warnings",
            "--input-type=module",
            "-e",
            script,
            str(WEB / "lib" / "auth" / "templateSecrets.ts"),
            value,
            node_env,
            str(min_length),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.stdout)


@needs_node
def test_production_keeps_template_secrets_out() -> None:
    for value in TEMPLATE_VALUES:
        assert configured(value, "production") is None
        assert configured(value, "development") == value
    assert configured("short-secret", "production", 32) is None
    assert configured("x" * 40, "production", 32) == "x" * 40
    assert configured("", "development") is None


def test_nexus_shows_no_cockpit_password() -> None:
    from naas_abi_marketplace.domains.finance.apps.financial_cockpit import ABIModule

    manifest = json.loads((APP / "manifest.json").read_text(encoding="utf-8"))

    assert "demo_password" not in manifest
    assert ABIModule.Configuration.model_fields["demo_password"].default == ""
