"""A browser-less client of the provider's pages, for the tests."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from starlette.testclient import TestClient

from naas_abi_idp.web import IdPWeb

HOST = "http://localhost:9879"
ROOT = "/idp"
REDIRECT = "http://localhost:9879/api/auth/oidc/callback"


def s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class Pkce:
    def __init__(self) -> None:
        self.verifier = secrets.token_urlsafe(48)
        self.challenge = s256(self.verifier)
        self.state = secrets.token_urlsafe(12)
        self.nonce = secrets.token_urlsafe(12)


def browser(service, **headers) -> TestClient:
    app = IdPWeb(service).app()
    client = TestClient(
        app,
        base_url=HOST,
        root_path=ROOT,
        follow_redirects=False,
        headers={"x-abi-client-ip": "10.1.2.3", **headers},
    )
    return client


def authorize_params(pkce: Pkce, **overrides) -> dict[str, str]:
    params = {
        "response_type": "code",
        "client_id": "abi",
        "redirect_uri": REDIRECT,
        "scope": "openid email profile groups offline_access",
        "state": pkce.state,
        "nonce": pkce.nonce,
        "code_challenge": pkce.challenge,
        "code_challenge_method": "S256",
    }
    params.update(overrides)
    return {k: v for k, v in params.items() if v is not None}


def csrf_of(html: str) -> str:
    found = re.search(r'name="csrf" value="([^"]+)"', html)
    assert found, html
    return found.group(1)


def start(client: TestClient, params: dict[str, str]) -> httpx.Response:
    return client.get(f"{ROOT}/authorize?{urlencode(params)}")


def sign_in(client, mailer, email: str, params: dict[str, str]) -> httpx.Response:
    """Authorize, ask for a code, enter it. Returns the final response."""
    page = start(client, params)
    assert page.status_code == 200, page.text
    csrf = csrf_of(page.text)
    sent = client.post(f"{ROOT}/login/email", data={"csrf": csrf, "email": email})
    assert sent.status_code == 200, sent.text
    code = mailer.last_code(email)
    return client.post(
        f"{ROOT}/login/code", data={"csrf": csrf, "email": email, "code": code}
    )


def callback_query(response: httpx.Response) -> dict[str, list[str]]:
    assert response.status_code == 302, response.text
    return parse_qs(urlsplit(response.headers["location"]).query)


def token(client, form: dict[str, str], *, auth: tuple[str, str] | None = None):
    return client.post(f"{ROOT}/token", data=form, auth=auth)
