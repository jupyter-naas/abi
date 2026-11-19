"""``Settings``: the portal sign-in secrets as the environment and ``.env`` give them."""

from __future__ import annotations

import logging

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import Settings, settings_environment
from naas_abi.apps.nexus.apps.api.app.services.apps.pages_sso import shared_secret_warning

PAGES_SSO_LOG = "naas_abi.apps.nexus.apps.api.app.services.apps.pages_sso"


@pytest.fixture
def no_portal_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """No ``PAGES_SSO_*`` in the environment, and a working directory of our own
    (``Settings`` reads ``.env`` there)."""
    for name in ("PAGES_SSO_SECRET", "PAGES_SSO_SECRETS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "raw",
    [
        "zq-bare-secret",  # PAGES_SSO_SECRET renamed, the bare secret kept
        '["zq-bare-secret"]',
        '{"acme.portal:site": 7}',
        '"zq-bare-secret"',
    ],
)
def test_a_malformed_portal_secrets_value_starts_with_none_and_says_so(
    no_portal_env, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, raw: str
) -> None:
    """Nexus starts: portal sign-in is off, with an error naming the expected
    shape and never the value."""
    monkeypatch.setenv("PAGES_SSO_SECRETS", raw)
    with caplog.at_level(logging.ERROR, logger=PAGES_SSO_LOG):
        settings = Settings()
    assert settings.pages_sso_secrets == {}
    said = [r.getMessage() for r in caplog.records if r.name == PAGES_SSO_LOG]
    assert said and '{"<module_path>:<app_dir>": "<secret>"}' in said[0], said
    assert not any("zq-bare-secret" in line for line in said)


def test_a_malformed_value_in_dot_env_starts_too(no_portal_env) -> None:
    (no_portal_env / ".env").write_text("PAGES_SSO_SECRETS=zq-bare-secret\n")
    assert Settings().pages_sso_secrets == {}


def test_the_yaml_map_wins_over_a_malformed_environment(
    no_portal_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAGES_SSO_SECRETS", "zq-bare-secret")
    settings = Settings(pages_sso_secrets={"acme.portal:site": "from-yaml"})
    assert settings.pages_sso_secrets == {"acme.portal:site": "from-yaml"}


def test_portal_secrets_are_read_from_dot_env(no_portal_env) -> None:
    (no_portal_env / ".env").write_text(
        'PAGES_SSO_SECRETS=\'{"acme.portal:site": "from-dot-env"}\'\n'
    )
    assert Settings().pages_sso_secrets == {"acme.portal:site": "from-dot-env"}


def test_the_shared_secret_kept_only_in_dot_env_is_said_at_start(
    no_portal_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Settings`` read ``PAGES_SSO_SECRET`` from ``.env`` as well, and neither
    ``abi dev up`` nor the engine copies ``.env`` into the process environment."""
    assert shared_secret_warning(settings_environment()) is None
    (no_portal_env / ".env").write_text("PAGES_SSO_SECRET=zq-old-shared\n")
    message = shared_secret_warning(settings_environment())
    assert message is not None and "pages_sso_secrets" in message
    assert "zq-old-shared" not in message


def test_the_process_environment_wins_over_dot_env(
    no_portal_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    (no_portal_env / ".env").write_text("PAGES_SSO_SECRET=from-file\nOTHER=file\n")
    monkeypatch.setenv("OTHER", "process")
    seen = settings_environment()
    assert seen["PAGES_SSO_SECRET"] == "from-file"
    assert seen["OTHER"] == "process"
    assert settings_environment({"OTHER": "given"})["OTHER"] == "given"
