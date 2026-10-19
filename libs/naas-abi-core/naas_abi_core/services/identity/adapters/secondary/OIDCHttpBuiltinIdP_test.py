import json

import pytest

from naas_abi_core.services.identity.adapters.secondary.OIDCHttpBuiltinIdP import (
    AppAnswer,
    OIDCHttpBuiltinIdP,
    below_issuer,
)
from naas_abi_core.services.identity.IdentityPorts import (
    HttpJSON,
    OIDCHttpPort,
    ProviderUnavailableError,
)

ISSUER = "https://abi.example/idp"


class Fallback(OIDCHttpPort):
    def __init__(self):
        self.calls = []

    def get_json(self, url):
        self.calls.append(("GET", url))
        return HttpJSON({"from": "http"}, None)

    def post_form(self, url, data, *, basic_auth=None):
        self.calls.append(("POST", url))
        return 200, {"from": "http"}


class App:
    def __init__(self, answer=None):
        self.requests = []
        self.answer = answer or AppAnswer(
            200, (("Cache-Control", "public, max-age=120"),), b'{"issuer": "x"}'
        )

    def request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))
        return self.answer


@pytest.mark.parametrize(
    "url, expected",
    [
        (ISSUER, "/"),
        (f"{ISSUER}/", "/"),
        (f"{ISSUER}/jwks.json", "/jwks.json"),
        (
            f"{ISSUER}/.well-known/openid-configuration",
            "/.well-known/openid-configuration",
        ),
        (f"{ISSUER}/token?x=1", "/token"),
        ("https://abi.example/idpx/jwks.json", None),
        ("https://abi.example/other", None),
        ("https://evil.example/idp/jwks.json", None),
        ("http://abi.example/idp/jwks.json", None),
        (f"{ISSUER}/../admin", None),
        (f"{ISSUER}/a/./b", None),
        (f"{ISSUER}/%2e%2e/admin", None),
        (f"{ISSUER}/a\\b", None),
        (f"{ISSUER}//admin", None),
    ],
)
def test_a_url_is_the_idps_only_when_it_is_below_its_issuer(url, expected):
    assert below_issuer(url, ISSUER) == expected


def test_the_idp_is_read_through_its_app_and_the_rest_over_http():
    fallback, app = Fallback(), App()
    port = OIDCHttpBuiltinIdP(fallback, [ISSUER])
    port.attach(app)
    document = port.get_json(f"{ISSUER}/.well-known/openid-configuration")
    assert document.body == {"issuer": "x"} and document.max_age == 120
    method, path, kwargs = app.requests[0]
    assert (method, path, kwargs["root_path"]) == (
        "GET",
        "/.well-known/openid-configuration",
        "/idp",
    )
    assert fallback.calls == []
    assert port.get_json("https://acme.okta.com/jwks").body == {"from": "http"}
    assert fallback.calls == [("GET", "https://acme.okta.com/jwks")]


def test_a_token_request_carries_the_form_and_the_clients_credentials():
    app = App(AppAnswer(200, (), json.dumps({"access_token": "t"}).encode()))
    port = OIDCHttpBuiltinIdP(Fallback(), [ISSUER])
    port.attach(app)
    status, body = port.post_form(
        f"{ISSUER}/token",
        {"grant_type": "authorization_code", "code": "c"},
        basic_auth=("abi", "s"),
    )
    assert (status, body) == (200, {"access_token": "t"})
    _, path, kwargs = app.requests[0]
    assert path == "/token"
    assert kwargs["body"] == b"grant_type=authorization_code&code=c"
    assert kwargs["headers"]["authorization"] == "Basic YWJpOnM="
    assert kwargs["headers"]["content-type"] == "application/x-www-form-urlencoded"


def test_an_error_answer_keeps_its_status_and_a_server_error_is_an_outage():
    port = OIDCHttpBuiltinIdP(Fallback(), [ISSUER])
    port.attach(App(AppAnswer(400, (), b'{"error": "invalid_grant"}')))
    assert port.post_form(f"{ISSUER}/token", {}) == (400, {"error": "invalid_grant"})
    port.attach(App(AppAnswer(401, (), b"")))
    assert port.post_form(f"{ISSUER}/token", {}) == (401, {})
    port.attach(App(AppAnswer(503, (), b"")))
    with pytest.raises(ProviderUnavailableError):
        port.post_form(f"{ISSUER}/token", {})
    with pytest.raises(ProviderUnavailableError):
        port.get_json(f"{ISSUER}/jwks.json")


def test_a_document_that_is_not_json_is_refused():
    port = OIDCHttpBuiltinIdP(Fallback(), [ISSUER])
    for body in (b"<html>", b"[1]", b"x" * (1024 * 1024 + 1)):
        port.attach(App(AppAnswer(200, (), body)))
        with pytest.raises(ProviderUnavailableError):
            port.get_json(f"{ISSUER}/jwks.json")


def test_before_the_app_is_attached_the_idp_is_down_and_never_fetched_over_http():
    fallback = Fallback()
    port = OIDCHttpBuiltinIdP(fallback, [ISSUER])
    with pytest.raises(ProviderUnavailableError, match="not reachable yet"):
        port.get_json(f"{ISSUER}/jwks.json")
    with pytest.raises(ProviderUnavailableError):
        port.post_form(f"{ISSUER}/token", {})
    assert fallback.calls == []
