from __future__ import annotations

from naas_abi_marketplace.applications.github.integrations.GitHubAppAuth import (
    app_slug,
    install_url,
    normalize_private_key,
)


def test_normalize_private_key_unescapes_dotenv_newlines() -> None:
    raw = "-----BEGIN RSA PRIVATE KEY-----\\nABC\\n-----END RSA PRIVATE KEY-----"
    pem = normalize_private_key(raw)
    assert "\nABC\n" in pem
    assert "\\n" not in pem


def test_app_slug_from_public_link(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_APP_SLUG", raising=False)
    monkeypatch.setenv("GITHUB_APP_PUBLIC_LINK", "https://github.com/apps/naasai-abi")
    assert app_slug() == "naasai-abi"


def test_install_url_includes_state(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_APP_SLUG", "naasai-abi")
    url = install_url(state="abc123")
    assert url.startswith("https://github.com/apps/naasai-abi/installations/new")
    assert "state=abc123" in url
