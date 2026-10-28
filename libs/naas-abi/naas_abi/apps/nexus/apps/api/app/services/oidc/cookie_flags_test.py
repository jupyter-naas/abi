"""The sign-in cookies are Secure, but for a deployment on plain http locally."""

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.primary import (
    oidc__primary_adapter__FastAPI as oidc_api,
)


@pytest.mark.parametrize(
    ("frontend_url", "secure"),
    [
        ("https://abi.example.com", True),
        ("https://localhost:3000", True),
        ("http://abi.example.com", True),  # plain http anywhere but here
        ("http://localhost:3000", False),
        ("http://127.0.0.1:12136", False),
    ],
)
def test_cookies_are_secure_unless_served_over_http_locally(
    monkeypatch, frontend_url: str, secure: bool
) -> None:
    monkeypatch.setattr(settings, "frontend_url", frontend_url)

    assert oidc_api._cookie_options()["secure"] is secure
    assert oidc_api._cookie_options()["httponly"] is True
