"""Settings gating for the local-dev browser auto-login.

These credentials are served to anonymous callers by `/api/auth/config`, so
the point of every test here is that they only ever survive on a local dev
stack. `Settings.model_post_init` is the single choke point — the endpoint
just reads `dev_autologin_enabled`.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.config import Settings

DEV_CREDS = {
    "dev_autologin_email": "admin@example.com",
    "dev_autologin_password": "generated-pw",
}


def test_autologin_survives_on_a_local_dev_stack() -> None:
    settings = Settings(
        environment="development",
        nexus_env="local",
        auth_password_enabled=True,
        **DEV_CREDS,
    )

    assert settings.dev_autologin_enabled
    assert settings.dev_autologin_email == "admin@example.com"


def test_autologin_is_stripped_in_production() -> None:
    """The credentials must not reach the browser off a real deployment."""
    settings = Settings(
        environment="production",
        nexus_env="cloudflare",
        auth_password_enabled=True,
        **DEV_CREDS,
    )

    assert not settings.dev_autologin_enabled
    assert settings.dev_autologin_email == ""
    assert settings.dev_autologin_password == ""


def test_autologin_is_stripped_when_password_auth_is_off() -> None:
    """Without the password flow there is nothing for the page to submit."""
    settings = Settings(
        environment="development",
        nexus_env="local",
        auth_password_enabled=False,
        **DEV_CREDS,
    )

    assert not settings.dev_autologin_enabled


def test_autologin_is_off_by_default() -> None:
    settings = Settings(environment="development", nexus_env="local")

    assert not settings.dev_autologin_enabled


def test_autologin_reads_the_env_vars_the_cli_sets(monkeypatch) -> None:
    """The contract with `abi dev up`, which sets exactly these names.

    Everything else here constructs Settings directly, which would happily
    keep passing if the env var names drifted apart.
    """
    monkeypatch.setenv("DEV_AUTOLOGIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("DEV_AUTOLOGIN_PASSWORD", "generated-pw")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AUTH_PASSWORD_ENABLED", "true")

    settings = Settings()

    assert settings.dev_autologin_enabled
    assert settings.dev_autologin_email == "admin@example.com"
    assert settings.dev_autologin_password == "generated-pw"


def test_autologin_needs_both_halves() -> None:
    settings = Settings(
        environment="development",
        nexus_env="local",
        auth_password_enabled=True,
        dev_autologin_email="admin@example.com",
    )

    assert not settings.dev_autologin_enabled
