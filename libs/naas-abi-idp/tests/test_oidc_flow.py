import base64
import json

import pytest
from support import (
    REDIRECT,
    ROOT,
    Pkce,
    authorize_params,
    browser,
    callback_query,
    csrf_of,
    sign_in,
    start,
    token,
)
from tests_helpers import verify_jwt

from naas_abi_idp.oidc import allow_local_issuer

ABI = ("abi", "abi-secret-abi-secret")


@pytest.fixture
def client(service):
    allow_local_issuer(service.configuration.issuer)
    return browser(service)


@pytest.fixture
def alice(service):
    service.create_group("Data readers")
    return service.create_user("alice@example.com", groups=["Data readers"])


def exchange(client, pkce, query, **overrides):
    form = {
        "grant_type": "authorization_code",
        "code": query["code"][0],
        "redirect_uri": REDIRECT,
        "code_verifier": pkce.verifier,
    }
    form.update(overrides)
    return token(client, form, auth=ABI)


def signed_in(client, mailer, pkce=None, **overrides):
    pkce = pkce or Pkce()
    done = sign_in(
        client, mailer, "alice@example.com", authorize_params(pkce, **overrides)
    )
    return pkce, callback_query(done)


def test_discovery_and_the_jwks(client, service):
    document = client.get(f"{ROOT}/.well-known/openid-configuration").json()
    assert document["issuer"] == service.configuration.issuer
    assert (
        document["authorization_endpoint"]
        == f"{service.configuration.issuer}/authorize"
    )
    assert document["code_challenge_methods_supported"] == ["S256"]
    assert document["id_token_signing_alg_values_supported"] == ["ES256"]
    assert "introspection_endpoint" not in document
    keys = client.get(document["jwks_uri"].replace("http://localhost:9879", "")).json()[
        "keys"
    ]
    assert keys[0]["kty"] == "EC" and keys[0]["alg"] == "ES256" and "d" not in keys[0]


def test_a_code_sign_in_gives_an_id_token_for_the_client(
    client, service, mailer, alice
):
    pkce, query = signed_in(client, mailer)
    assert query["state"] == [pkce.state]
    response = exchange(client, pkce, query)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "Bearer" and body["refresh_token"]
    assert body["expires_in"] <= 600
    claims = verify_jwt(service, body["id_token"], audience="abi")
    assert claims["sub"] == alice.id
    assert claims["email"] == "alice@example.com" and claims["email_verified"] is True
    assert claims["nonce"] == pkce.nonce
    assert claims["groups"] == ["Data readers"]
    assert claims["iss"] == service.configuration.issuer
    assert claims["exp"] - claims["iat"] <= 600
    access = verify_jwt(
        service, body["access_token"], audience=service.configuration.issuer
    )
    assert access["sub"] == alice.id and access["client_id"] == "abi"


def test_the_login_pages_are_locked_down(client, mailer, alice):
    page = start(client, authorize_params(Pkce()))
    assert page.headers["cache-control"] == "no-store"
    csp = page.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
    assert "script-src" not in csp and "<script" not in page.text
    assert "form-action 'self' http://localhost:9879" in csp
    cookie = page.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/idp" in cookie


def test_the_provider_session_signs_in_again_without_a_code(
    client, service, mailer, alice
):
    signed_in(client, mailer)
    again = start(client, authorize_params(Pkce()))
    assert again.status_code == 302
    assert "code=" in again.headers["location"]
    forced = start(client, authorize_params(Pkce(), prompt="login"))
    assert forced.status_code == 200  # asked to authenticate again
    silent = start(client, authorize_params(Pkce(), prompt="none"))
    assert "code=" in silent.headers["location"]


def test_prompt_none_without_a_session_is_login_required(client):
    response = start(client, authorize_params(Pkce(), prompt="none"))
    assert response.status_code == 302
    assert "error=login_required" in response.headers["location"]


def test_pkce_is_required_and_only_s256(client):
    for overrides in (
        {"code_challenge": None, "code_challenge_method": None},
        {"code_challenge_method": "plain"},
        {"code_challenge_method": None},
    ):
        response = start(client, authorize_params(Pkce(), **overrides))
        assert response.status_code == 302, overrides
        assert "error=invalid_request" in response.headers["location"], overrides


def test_a_request_with_an_unregistered_redirect_never_redirects(client):
    response = start(
        client, authorize_params(Pkce(), redirect_uri="https://evil.example/cb")
    )
    assert response.status_code == 400
    assert "location" not in response.headers
    prefix = authorize_params(Pkce(), redirect_uri=REDIRECT + "/../x")
    assert start(client, prefix).status_code == 400
    assert start(client, authorize_params(Pkce(), client_id="nope")).status_code == 400


def test_a_repeated_parameter_is_refused(client):
    pkce = Pkce()
    query = "&".join(f"{k}={v}" for k, v in authorize_params(pkce).items())
    response = client.get(f"{ROOT}/authorize?{query}&state=other")
    assert response.status_code == 400


def test_the_wrong_verifier_burns_the_code(client, mailer, alice):
    pkce, query = signed_in(client, mailer)
    wrong = exchange(client, pkce, query, code_verifier=Pkce().verifier)
    assert wrong.status_code == 400 and wrong.json()["error"] == "invalid_grant"
    again = exchange(client, pkce, query)
    assert again.status_code == 400  # the right verifier no longer helps


def test_a_code_works_once_and_its_reuse_revokes_what_it_issued(client, mailer, alice):
    pkce, query = signed_in(client, mailer)
    first = exchange(client, pkce, query)
    assert first.status_code == 200
    replay = exchange(client, pkce, query)
    assert replay.status_code == 400
    refreshed = token(
        client,
        {"grant_type": "refresh_token", "refresh_token": first.json()["refresh_token"]},
        auth=ABI,
    )
    assert refreshed.status_code == 400  # RFC 6749 4.1.2


def test_a_code_belongs_to_its_redirect_and_client(client, mailer, alice):
    pkce, query = signed_in(client, mailer)
    other = exchange(client, pkce, query, redirect_uri="http://localhost:9879/other")
    assert other.status_code == 400


def test_a_code_expires(client, service, mailer, clock, alice):
    pkce, query = signed_in(client, mailer)
    clock.advance(service.configuration.authorization_code_seconds + 1)
    assert exchange(client, pkce, query).status_code == 400


def test_the_client_must_authenticate(client, mailer, alice):
    pkce, query = signed_in(client, mailer)
    anonymous = token(
        client,
        {
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": REDIRECT,
            "code_verifier": pkce.verifier,
            "client_id": "abi",
        },
    )
    assert anonymous.status_code == 401
    wrong = exchange(client, pkce, query)  # the code survived the failed attempt
    assert wrong.status_code in (200, 400)


def test_a_public_client_signs_in_with_pkce_alone(client, mailer, alice):
    pkce = Pkce()
    params = authorize_params(
        pkce, client_id="public-app", redirect_uri="http://localhost:3000/callback"
    )
    query = callback_query(sign_in(client, mailer, "alice@example.com", params))
    response = token(
        client,
        {
            "grant_type": "authorization_code",
            "client_id": "public-app",
            "code": query["code"][0],
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": pkce.verifier,
        },
    )
    assert response.status_code == 200, response.text


def test_refresh_tokens_rotate_and_a_replay_revokes_the_family(
    client, service, mailer, alice
):
    pkce, query = signed_in(client, mailer)
    first = exchange(client, pkce, query).json()
    form = {"grant_type": "refresh_token", "refresh_token": first["refresh_token"]}
    second = token(client, form, auth=ABI)
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["refresh_token"] != first["refresh_token"]
    claims = verify_jwt(service, body["id_token"], audience="abi")
    assert claims["sub"] == alice.id
    # The old token again: a copy was stolen. Everything in the family stops.
    assert token(client, form, auth=ABI).status_code == 400
    again = token(
        client,
        {"grant_type": "refresh_token", "refresh_token": body["refresh_token"]},
        auth=ABI,
    )
    assert again.status_code == 400


def test_a_refresh_token_is_for_its_client(client, mailer, alice):
    pkce, query = signed_in(client, mailer)
    first = exchange(client, pkce, query).json()
    other = token(
        client,
        {"grant_type": "refresh_token", "refresh_token": first["refresh_token"]},
        auth=("robot", "robot-secret-robot-secret"),
    )
    assert other.status_code in (400, 401)


def test_a_refresh_token_expires(client, service, mailer, clock, alice):
    pkce, query = signed_in(client, mailer)
    first = exchange(client, pkce, query).json()
    clock.advance(service.configuration.refresh_token_days * 86400 + 1)
    response = token(
        client,
        {"grant_type": "refresh_token", "refresh_token": first["refresh_token"]},
        auth=ABI,
    )
    assert response.status_code == 400


def test_revocation_ends_the_grant(client, mailer, alice):
    pkce, query = signed_in(client, mailer)
    first = exchange(client, pkce, query).json()
    revoked = client.post(
        f"{ROOT}/revoke", data={"token": first["refresh_token"]}, auth=ABI
    )
    assert revoked.status_code == 200
    refresh = token(
        client,
        {"grant_type": "refresh_token", "refresh_token": first["refresh_token"]},
        auth=ABI,
    )
    assert refresh.status_code == 400
    # An unknown token is accepted, as RFC 7009 says.
    assert (
        client.post(f"{ROOT}/revoke", data={"token": "nope"}, auth=ABI).status_code
        == 200
    )


def test_a_disabled_user_cannot_refresh_or_use_userinfo(client, service, mailer, alice):
    pkce, query = signed_in(client, mailer)
    first = exchange(client, pkce, query).json()
    service.set_disabled(alice.id, True)
    refresh = token(
        client,
        {"grant_type": "refresh_token", "refresh_token": first["refresh_token"]},
        auth=ABI,
    )
    assert refresh.status_code == 400
    info = client.get(
        f"{ROOT}/userinfo", headers={"authorization": f"Bearer {first['access_token']}"}
    )
    assert info.status_code == 401


def test_userinfo_answers_for_the_scopes_of_the_token(client, mailer, alice):
    pkce, query = signed_in(client, mailer)
    first = exchange(client, pkce, query).json()
    info = client.get(
        f"{ROOT}/userinfo", headers={"authorization": f"Bearer {first['access_token']}"}
    )
    assert info.status_code == 200
    assert info.json() == {
        "sub": alice.id,
        "email": "alice@example.com",
        "email_verified": True,
        "name": "Alice",
        "preferred_username": "alice@example.com",
        "groups": ["Data readers"],
    }
    assert client.get(f"{ROOT}/userinfo").status_code == 401
    forged = first["access_token"].rsplit(".", 1)[0] + ".AAAA"
    assert (
        client.get(
            f"{ROOT}/userinfo", headers={"authorization": f"Bearer {forged}"}
        ).status_code
        == 401
    )


def test_an_access_token_expires_in_ten_minutes_at_most(
    client, service, mailer, clock, alice
):
    pkce, query = signed_in(client, mailer)
    first = exchange(client, pkce, query).json()
    clock.advance(601)
    info = client.get(
        f"{ROOT}/userinfo", headers={"authorization": f"Bearer {first['access_token']}"}
    )
    assert info.status_code == 401


def test_client_credentials_for_a_service_account(client, service):
    response = token(
        client,
        {"grant_type": "client_credentials", "scope": "jobs"},
        auth=("robot", "robot-secret-robot-secret"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "refresh_token" not in body and "id_token" not in body
    claims = verify_jwt(
        service, body["access_token"], audience=service.configuration.issuer
    )
    assert claims["sub"] == "robot" and claims["scope"] == "jobs"
    # A robot is no user: userinfo does not answer for it.
    assert (
        client.get(
            f"{ROOT}/userinfo",
            headers={"authorization": f"Bearer {body['access_token']}"},
        ).status_code
        == 401
    )
    bad = token(client, {"grant_type": "client_credentials"}, auth=("robot", "wrong"))
    assert bad.status_code == 401
    # A client of user sign-ins cannot use the grant.
    assert (
        token(client, {"grant_type": "client_credentials"}, auth=ABI).status_code == 400
    )


def test_a_client_created_through_the_admin_api_signs_robots_in(client, service):
    created, secret = service.create_client("ci", scopes=["jobs"])
    response = token(
        client, {"grant_type": "client_credentials"}, auth=(created.client_id, secret)
    )
    assert response.status_code == 200
    service.set_client_disabled(created.client_id, True)
    assert (
        token(
            client,
            {"grant_type": "client_credentials"},
            auth=(created.client_id, secret),
        ).status_code
        == 401
    )


def test_the_token_endpoint_reads_forms_only(client):
    post = client.post(
        f"{ROOT}/token",
        content=json.dumps({"grant_type": "client_credentials"}),
        headers={"content-type": "application/json"},
        auth=("robot", "robot-secret-robot-secret"),
    )
    assert post.status_code == 400
    twice = client.post(
        f"{ROOT}/token",
        content="grant_type=client_credentials&grant_type=refresh_token",
        headers={"content-type": "application/x-www-form-urlencoded"},
        auth=("robot", "robot-secret-robot-secret"),
    )
    assert twice.status_code == 400


def test_a_wrong_csrf_token_signs_nobody_in(client, mailer, alice):
    page = start(client, authorize_params(Pkce()))
    csrf_of(page.text)
    response = client.post(
        f"{ROOT}/login/email", data={"csrf": "forged", "email": "alice@example.com"}
    )
    assert response.status_code == 400
    assert mailer.sent == []


def test_login_without_the_cookie_is_expired(service, mailer, alice):
    page = start(browser(service), authorize_params(Pkce()))
    csrf = csrf_of(page.text)
    other = browser(service)  # a browser that never started a sign-in
    response = other.post(
        f"{ROOT}/login/email", data={"csrf": csrf, "email": "alice@example.com"}
    )
    assert response.status_code == 400 and mailer.sent == []


def test_a_wrong_code_is_refused_and_counted(client, mailer, alice, service):
    page = start(client, authorize_params(Pkce()))
    csrf = csrf_of(page.text)
    client.post(
        f"{ROOT}/login/email", data={"csrf": csrf, "email": "alice@example.com"}
    )
    response = client.post(
        f"{ROOT}/login/code",
        data={"csrf": csrf, "email": "alice@example.com", "code": "000000"},
    )
    assert response.status_code == 400 and "not valid" in response.text
    for _ in range(service.configuration.max_attempts):
        last = client.post(
            f"{ROOT}/login/code",
            data={"csrf": csrf, "email": "alice@example.com", "code": "000001"},
        )
    assert last.status_code == 429 and "retry-after" in last.headers


def test_an_unknown_address_sees_the_same_page_as_a_known_one(client, mailer, alice):
    def code_page(email):
        page = start(client, authorize_params(Pkce()))
        out = client.post(
            f"{ROOT}/login/email", data={"csrf": csrf_of(page.text), "email": email}
        )
        return out.status_code, out.text.replace(email, "EMAIL")

    known, unknown = code_page("alice@example.com"), code_page("ghost@example.com")
    assert known[0] == unknown[0] == 200
    assert len(known[1]) - len(unknown[1]) < 200  # only the csrf token differs


def test_password_sign_in_when_enabled(client, service, mailer):
    service.configuration.password_login_enabled = True
    user = service.create_user("pat@example.com", password="correct horse battery")
    pkce = Pkce()
    page = start(client, authorize_params(pkce))
    assert "Use a password instead" in page.text
    csrf = csrf_of(page.text)
    assert client.get(f"{ROOT}/login/password").status_code == 200
    bad = client.post(
        f"{ROOT}/login/password",
        data={"csrf": csrf, "email": "pat@example.com", "password": "wrong password"},
    )
    assert bad.status_code == 400
    ok = client.post(
        f"{ROOT}/login/password",
        data={
            "csrf": csrf,
            "email": "pat@example.com",
            "password": "correct horse battery",
        },
    )
    query = callback_query(ok)
    response = exchange(client, pkce, query)
    assert (
        verify_jwt(service, response.json()["id_token"], audience="abi")["sub"]
        == user.id
    )


def test_password_sign_in_is_not_offered_by_default(client, service):
    page = start(client, authorize_params(Pkce()))
    assert "/login/password" not in page.text and "Use a password" not in page.text
    assert client.get(f"{ROOT}/login/password").status_code == 404


def test_logout_ends_the_session_and_redirects_only_to_the_clients_origin(
    client, service, mailer, alice
):
    pkce, query = signed_in(client, mailer)
    body = exchange(client, pkce, query).json()
    target = "http://localhost:9879/after"
    out = client.get(
        f"{ROOT}/logout",
        params={
            "id_token_hint": body["id_token"],
            "post_logout_redirect_uri": target,
            "state": "s",
        },
    )
    assert out.status_code == 302 and out.headers["location"].startswith(target)
    assert start(client, authorize_params(Pkce())).status_code == 200  # no session left
    away = client.get(
        f"{ROOT}/logout",
        params={
            "id_token_hint": body["id_token"],
            "post_logout_redirect_uri": "https://evil.example/",
        },
    )
    assert away.status_code == 200
    no_hint = client.get(f"{ROOT}/logout", params={"post_logout_redirect_uri": target})
    assert no_hint.status_code == 200


def test_the_id_token_header_names_its_key(client, service, mailer, alice):
    pkce, query = signed_in(client, mailer)
    id_token = exchange(client, pkce, query).json()["id_token"]
    header = json.loads(base64.urlsafe_b64decode(id_token.split(".")[0] + "=="))
    assert header["alg"] == "ES256" and header["kid"] == service.keys.active().kid


def test_the_branding_of_a_domain_shows_once_the_address_is_known(service, mailer):
    from naas_abi_idp.configuration import Branding

    service.configuration.domain_branding["acme.test"] = Branding.of(
        {
            "app_name": "Acme",
            "primary_color": "#ff0000",
            "logo_url": "https://acme.test/logo.png",
        },
        service.configuration.branding,
    )
    service.create_user("sam@acme.test")
    client = browser(service)
    default = start(client, authorize_params(Pkce()))
    assert "Acme" not in default.text
    out = client.post(
        f"{ROOT}/login/email",
        data={"csrf": csrf_of(default.text), "email": "sam@acme.test"},
    )
    assert "#ff0000" in out.text and "https://acme.test/logo.png" in out.text
    assert "Acme" in mailer.sent[-1].subject
