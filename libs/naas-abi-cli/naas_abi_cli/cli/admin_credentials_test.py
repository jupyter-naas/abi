from __future__ import annotations

import re
from pathlib import Path

import pytest

from naas_abi_cli.cli.admin_credentials import (
    ADMIN_EMAIL,
    ensure_api_key,
)


def _env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def test_the_seeded_admin_has_no_password() -> None:
    """Nexus has no login of its own: the admin signs in at the identity provider
    with a code mailed to its address, so no password is ever generated."""
    from naas_abi_cli.cli import admin_credentials

    assert ADMIN_EMAIL == "admin@example.com"
    for name in (
        "ensure_admin_credentials",
        "generate_admin_password",
        "ADMIN_PASSWORD_KEY",
        "ADMIN_EMAIL_KEY",
    ):
        assert not hasattr(admin_credentials, name)


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


def test_the_callout_seed_is_generated_once_with_its_issuer(tmp_path):
    from naas_abi_cli.cli.admin_credentials import (
        ensure_nats_callout_seed,
        nats_callout_issuer,
    )

    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")

    first = ensure_nats_callout_seed(env)
    second = ensure_nats_callout_seed(env)

    assert first == second and first.startswith("SA")
    issuer = nats_callout_issuer(first)
    assert issuer.startswith("A") and len(issuer) == 56
    text = env.read_text()
    assert f"NATS_AUTH_CALLOUT_SEED={first}" in text
    assert f"NATS_AUTH_CALLOUT_ISSUER={issuer}" in text
    assert "OTHER=1" in text


def test_a_seed_that_is_not_an_account_seed_is_replaced(tmp_path):
    from naas_abi_cli.cli.admin_credentials import ensure_nats_callout_seed

    env = tmp_path / ".env"
    env.write_text("NATS_AUTH_CALLOUT_SEED=not-a-seed\n")

    assert ensure_nats_callout_seed(env).startswith("SA")
    assert env.read_text().count("NATS_AUTH_CALLOUT_SEED=") == 1


def test_ensure_nats_passwords_generates_each_broker_user_once(tmp_path):
    from naas_abi_cli.cli.admin_credentials import ensure_nats_passwords

    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")

    first = ensure_nats_passwords(env)
    second = ensure_nats_passwords(env)

    assert first == second
    assert set(first) == {"NATS_ENGINE_PASSWORD", "NATS_AUTH_PASSWORD"}
    assert first["NATS_ENGINE_PASSWORD"] != first["NATS_AUTH_PASSWORD"]
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
    env.write_text(f"NATS_ENGINE_PASSWORD={value}\nNATS_AUTH_PASSWORD={'m' * 40}\n")

    passwords = ensure_nats_passwords(env)

    assert len(passwords["NATS_ENGINE_PASSWORD"]) >= 32
    assert passwords["NATS_AUTH_PASSWORD"] == "m" * 40
    assert env.read_text().count("NATS_ENGINE_PASSWORD=") == 1


@pytest.mark.parametrize(
    "url", ["nats://127.0.0.1:13042", "nats://abi:old-password@127.0.0.1:13042"]
)
def test_nats_login_puts_the_user_and_password_in_the_url(url):
    from naas_abi_cli.cli.admin_credentials import nats_login

    assert (
        nats_login(url, "module", "nats-pw_1")
        == "nats://module:nats-pw_1@127.0.0.1:13042"
    )
