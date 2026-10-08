from __future__ import annotations

import re
from pathlib import Path

import pytest

from naas_abi_cli.cli.admin_credentials import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD_KEY,
    ensure_admin_credentials,
    ensure_api_key,
)


def _env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def test_admin_password_is_generated_when_missing(tmp_path: Path) -> None:
    env = tmp_path / ".env"

    email, password = ensure_admin_credentials(env)

    assert email == ADMIN_EMAIL
    assert len(password) >= 24
    assert _env(env)[ADMIN_PASSWORD_KEY] == password
    assert _env(env)["NEXUS_USER_ADMIN_EXAMPLE_COM_EMAIL"] == ADMIN_EMAIL


def test_each_project_gets_a_different_password(tmp_path: Path) -> None:
    first = ensure_admin_credentials(tmp_path / "a.env")[1]
    second = ensure_admin_credentials(tmp_path / "b.env")[1]

    assert first != second


@pytest.mark.parametrize("default", ["Admin1234!", "admin"])
def test_a_shipped_default_password_is_replaced_in_place(tmp_path: Path, default: str) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "OTHER=1\n"
        f"NEXUS_USER_ADMIN_PASSWORD={default}\n"
        f"{ADMIN_PASSWORD_KEY}={default}\n"
        "LAST=2\n"
    )

    _email, password = ensure_admin_credentials(env)

    values = _env(env)
    assert password != default
    assert values[ADMIN_PASSWORD_KEY] == password
    assert "NEXUS_USER_ADMIN_PASSWORD" not in values
    assert values["OTHER"] == "1" and values["LAST"] == "2"
    assert env.read_text().count(ADMIN_PASSWORD_KEY) == 1


def test_a_custom_password_is_kept(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(f"{ADMIN_PASSWORD_KEY}=my-own-strong-pw\n")

    assert ensure_admin_credentials(env)[1] == "my-own-strong-pw"


@pytest.mark.parametrize("existing", [None, "abi"])
def test_api_key_is_generated_instead_of_the_old_default(
    tmp_path: Path, existing: str | None
) -> None:
    env = tmp_path / ".env"
    if existing:
        env.write_text(f"ABI_API_KEY={existing}\n")

    key = ensure_api_key(env)

    assert key != "abi"
    assert len(key) >= 32
    assert _env(env)["ABI_API_KEY"] == key


def test_a_custom_api_key_is_kept(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("ABI_API_KEY=configured-key\n")

    assert ensure_api_key(env) == "configured-key"


def test_ensure_nats_secret_generates_once_and_keeps_it(tmp_path):
    from naas_abi_cli.cli.admin_credentials import ensure_nats_secret

    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")

    first = ensure_nats_secret(env)
    second = ensure_nats_secret(env)

    assert first == second and len(first) >= 32
    assert "OTHER=1" in env.read_text()
    assert f"NATS_JWT_SECRET={first}" in env.read_text()


def test_ensure_nats_secret_keeps_an_existing_value(tmp_path):
    from naas_abi_cli.cli.admin_credentials import ensure_nats_secret

    env = tmp_path / ".env"
    env.write_text("NATS_JWT_SECRET=" + "k" * 40 + "\n")

    assert ensure_nats_secret(env) == "k" * 40


def test_ensure_nats_passwords_generates_each_broker_user_once(tmp_path):
    from naas_abi_cli.cli.admin_credentials import ensure_nats_passwords

    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")

    first = ensure_nats_passwords(env)
    second = ensure_nats_passwords(env)

    assert first == second
    assert set(first) == {"NATS_ABI_PASSWORD", "NATS_MODULE_PASSWORD"}
    assert first["NATS_ABI_PASSWORD"] != first["NATS_MODULE_PASSWORD"]
    for key, password in first.items():
        assert f"{key}={password}" in env.read_text()
        # nats.conf reads it as a config value ($VAR): it must start with a
        # letter, and nats://user:password@host must not need escaping.
        assert password[0].isalpha() and len(password) >= 32
        assert re.fullmatch(r"[A-Za-z0-9_-]+", password)
    assert "OTHER=1" in env.read_text()


@pytest.mark.parametrize("value", ["", "short"])
def test_ensure_nats_passwords_replaces_an_empty_or_short_password(tmp_path, value):
    """An empty password lets anyone in as that broker user."""
    from naas_abi_cli.cli.admin_credentials import ensure_nats_passwords

    env = tmp_path / ".env"
    env.write_text(f"NATS_ABI_PASSWORD={value}\nNATS_MODULE_PASSWORD={'m' * 40}\n")

    passwords = ensure_nats_passwords(env)

    assert len(passwords["NATS_ABI_PASSWORD"]) >= 32
    assert passwords["NATS_MODULE_PASSWORD"] == "m" * 40
    assert env.read_text().count("NATS_ABI_PASSWORD=") == 1
