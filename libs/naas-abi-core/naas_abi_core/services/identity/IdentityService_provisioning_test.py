"""Provisioning and invitations at sign-in: who may provision, what
each adapter does, and what a first sign-in claims."""

from __future__ import annotations

import json
import secrets
from typing import Any

import httpx
import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Identity import (
    IdentityConfiguration,
)
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import document, statement
from naas_abi_core.services.identity.adapters.secondary.AdminHttp import (
    AdminHttp,
    ClientCredentialsToken,
)
from naas_abi_core.services.identity.adapters.secondary.OIDCHttpHttpx import (
    OIDCHttpHttpx,
)
from naas_abi_core.services.identity.adapters.secondary.ProvisioningBuiltinIdP import (
    ProvisioningBuiltinIdP,
)
from naas_abi_core.services.identity.adapters.secondary.ProvisioningKeycloak import (
    ProvisioningKeycloak,
    admin_location,
)
from naas_abi_core.services.identity.IdentityPorts import (
    IdentityProvider,
    ProviderUnavailableError,
    ProvisionedUser,
    ProvisioningError,
    ProvisioningNone,
    ProvisioningPort,
)
from naas_abi_core.services.identity.IdentityService import IdentityService
from naas_abi_core.services.identity.tests.builtin_idp_server import AdminApp
from naas_abi_core.services.identity.tests.fake_idp import FakeIdP
from naas_abi_core.services.identity.tests.identity_contract import (
    CALLER,
    bootstrapped_iam,
    identity_service,
    sign_in,
)

W1 = "abi:acme:ws1"


def address() -> str:
    return f"invitee-{secrets.token_hex(3)}@example.com"


class Recorder(ProvisioningPort):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def ensure_user(self, email: str, *, name: str | None = None) -> ProvisionedUser:
        self.calls.append(("ensure", email, name))
        return ProvisionedUser("p", email, "sub-1", name, created=True)

    def find_user(self, email: str) -> ProvisionedUser | None:
        self.calls.append(("find", email, None))
        return None


def service_with(iam: IAMService, *adapters: tuple[str, ProvisioningPort | None]):
    providers = [
        IdentityProvider(
            name=name,
            issuer=f"https://{name}.example.com",
            client_id="abi",
            provisioning="zitadel" if adapter else "none",
        )
        for name, adapter in adapters
    ]
    return IdentityService(
        providers,
        iam,
        OIDCHttpHttpx(),
        provisioning={n: a for n, a in adapters if a is not None},
    )


@pytest.fixture
def iam() -> IAMService:
    return bootstrapped_iam()


# -- the service ----------------------------------------------------------------------


def test_provisioning_is_checked_on_the_provider_and_normalizes_its_input(iam):
    adapter = Recorder()
    service = service_with(iam, ("acme", adapter), ("other", Recorder()))
    with as_service_account("api"):
        user = service.provision_user("acme", "  Bob@Example.COM ", name=" Bob ")
        assert user.created and (user.provider, user.email) == ("p", "bob@example.com")
        assert service.find_provisioned_user("acme", "BOB@example.com") is None
    assert adapter.calls == [
        ("ensure", "bob@example.com", "Bob"),
        ("find", "bob@example.com", None),
    ]
    with as_service_account("api"):
        for bad in ("nope", "", "a b@example.com", "@example.com", "x@"):
            with pytest.raises(ValueError):
                service.provision_user("acme", bad)
        with pytest.raises(ValueError):
            service.provision_user("acme", "bob@example.com", name="x" * 201)


def test_a_caller_with_no_policy_provisions_nobody(iam):
    adapter = Recorder()
    service = service_with(iam, ("acme", adapter))
    with as_service_account("module/acme/nobody"), pytest.raises(Exception) as denied:
        service.provision_user("acme", "bob@example.com")
    assert type(denied.value).__name__ in (
        "PermissionDeniedError",
        "UnknownProviderError",
        "ResourceNotFoundError",
    )
    assert adapter.calls == []


def test_a_caller_that_may_only_sign_in_cannot_provision(iam):
    adapter = Recorder()
    service = service_with(iam, ("acme", adapter))
    with as_service_account("engine"):
        account = iam.create_service_account("module/acme/relying-party")
        policy = iam.create_policy(
            "sign-in",
            document(
                statement(
                    "Allow",
                    [
                        "identity:SignIn",
                        "identity:GetProvider",
                        "identity:ListProviders",
                    ],
                    ["abi:-:-:identity:provider/*"],
                )
            ),
        )
        iam.attach_policy(policy.id, account.id)
    with as_service_account("module/acme/relying-party"):
        with pytest.raises(PermissionDeniedError):
            service.provision_user("acme", "bob@example.com")
        with pytest.raises(PermissionDeniedError):
            service.find_provisioned_user("acme", "bob@example.com")
    assert adapter.calls == []


def test_a_provider_managed_in_the_provider_raises_not_implemented(iam):
    service = service_with(iam, ("okta", None))
    with as_service_account(CALLER):
        with pytest.raises(NotImplementedError, match="managed in the identity"):
            service.provision_user("okta", "bob@example.com")
        with pytest.raises(NotImplementedError):
            service.find_provisioned_user("okta", "bob@example.com")
    assert (
        service.get_provider.__self__ is service
    )  # unaffected: it is still a provider
    with as_service_account(CALLER):
        assert service.get_provider("okta").provisioning == "none"


def test_the_none_adapter_never_provisions():
    with pytest.raises(NotImplementedError):
        ProvisioningNone("okta").ensure_user("bob@example.com")


# -- the built-in IdP ------------------------------------------------------------------


@pytest.fixture
def builtin():
    pytest.importorskip("naas_abi_idp")
    from naas_abi_idp.adapters.memory import (
        MemoryDocumentStore,
        MemoryMailer,
        MemorySecretStore,
    )
    from naas_abi_idp.configuration import IdPConfiguration
    from naas_abi_idp.service import IdPService

    idp = IdPService(
        MemoryDocumentStore(),
        MemorySecretStore(),
        MemoryMailer(),
        IdPConfiguration(issuer="http://127.0.0.1:9/idp"),
    )
    adapter = ProvisioningBuiltinIdP("builtin")
    adapter.attach(AdminApp(idp))
    return idp, adapter


def test_the_builtin_adapter_creates_the_user_in_the_idp(builtin):
    idp, adapter = builtin
    created = adapter.ensure_user("Bob@Example.com", name="Bob B")
    assert created.created is True and created.email == "bob@example.com"
    assert created.name == "Bob B" and created.subject.startswith("u_")
    assert idp.find_user("bob@example.com").id == created.subject
    again = adapter.ensure_user("bob@example.com")
    assert again.created is False and again.subject == created.subject
    found = adapter.find_user("bob@example.com")
    assert found is not None and found.subject == created.subject
    assert adapter.find_user("nobody@example.com") is None
    with pytest.raises(ValueError):
        adapter.ensure_user("not an email")


def test_the_builtin_adapter_finds_the_user_who_registered_themselves(builtin):
    idp, adapter = builtin
    registered = idp.create_user("self@example.com")
    ensured = adapter.ensure_user("self@example.com")
    assert ensured.created is False and ensured.subject == registered.id


def test_the_builtin_adapter_is_unavailable_until_attached():
    with pytest.raises(ProviderUnavailableError):
        ProvisioningBuiltinIdP("builtin").ensure_user("bob@example.com")


def test_the_idp_refuses_any_account_but_the_engines(builtin):
    idp, _ = builtin
    adapter = ProvisioningBuiltinIdP("builtin")
    adapter.attach(AdminApp(idp, name="module/acme/people"))
    with pytest.raises(ProvisioningError, match="refused this account"):
        adapter.ensure_user("bob@example.com")
    assert idp.find_user("bob@example.com") is None


# -- Keycloak -----------------------------------------------------------------------------


class FakeKeycloak:
    """The few Keycloak admin endpoints the adapter uses."""

    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.requests: list[tuple[str, str]] = []
        self.token_requests = 0
        self.mail_status = 204
        self.expires_in = 300

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, request.url.path))
        path = request.url.path
        if path.endswith("/protocol/openid-connect/token"):
            self.token_requests += 1
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(
                200,
                json={
                    "access_token": f"t{self.token_requests}",
                    "expires_in": self.expires_in,
                },
            )
        assert request.headers.get("authorization", "").startswith("Bearer t")
        base = "/kc/admin/realms/acme/users"
        if request.method == "GET" and path == base:
            email = request.url.params["email"]
            assert request.url.params["exact"] == "true"
            found = [u for u in self.users.values() if u["email"] == email]
            return httpx.Response(200, json=found)
        if request.method == "POST" and path == base:
            body = json.loads(request.content)
            if any(u["email"] == body["email"] for u in self.users.values()):
                return httpx.Response(409, json={"errorMessage": "exists"})
            user_id = f"kc-{len(self.users) + 1}"
            self.users[user_id] = {"id": user_id, **body}
            return httpx.Response(201, headers={"Location": f"{base}/{user_id}"})
        if request.method == "PUT" and path.endswith("/execute-actions-email"):
            assert json.loads(request.content) == ["VERIFY_EMAIL", "UPDATE_PASSWORD"]
            return httpx.Response(self.mail_status)
        return httpx.Response(404)


def keycloak(fake: FakeKeycloak, *, send_actions: bool = True, clock=None):
    transport = httpx.MockTransport(fake.handler)
    issuer = "https://id.example.com/kc/realms/acme"
    server, realm = admin_location(issuer, None, None)
    assert (server, realm) == ("https://id.example.com/kc", "acme")
    kwargs: dict[str, Any] = {"clock": clock} if clock else {}
    token = ClientCredentialsToken(
        f"{issuer}/protocol/openid-connect/token",
        "abi-admin",
        "s3cret",
        client=httpx.Client(transport=transport),
        **kwargs,
    )
    return ProvisioningKeycloak(
        "kc",
        AdminHttp(
            server, headers=token.headers, client=httpx.Client(transport=transport)
        ),
        realm,
        send_actions=send_actions,
    )


def test_keycloak_creates_an_unverified_user_and_mails_the_actions():
    fake = FakeKeycloak()
    adapter = keycloak(fake)
    created = adapter.ensure_user("bob@example.com", name="Bob Builder")
    assert (created.created, created.subject, created.name) == (
        True,
        "kc-1",
        "Bob Builder",
    )
    stored = fake.users["kc-1"]
    assert stored["emailVerified"] is False and stored["enabled"] is True
    assert stored["username"] == "bob@example.com"
    assert (
        "PUT",
        "/kc/admin/realms/acme/users/kc-1/execute-actions-email",
    ) in fake.requests
    again = adapter.ensure_user("bob@example.com")
    assert again.created is False and again.subject == "kc-1"
    assert adapter.find_user("nobody@example.com") is None
    assert fake.token_requests == 1  # one token served every call


def test_keycloak_without_a_mail_server_still_provisions_and_says_so():
    fake = FakeKeycloak()
    fake.mail_status = 400
    created = keycloak(fake).ensure_user("bob@example.com")
    assert created.created and created.subject == "kc-1"
    assert "could not send the verification email" in created.warning
    assert "HTTP 400" in created.warning


def test_keycloak_that_cannot_be_reached_for_the_mail_says_so():
    fake = FakeKeycloak()
    fake.mail_status = 503
    created = keycloak(fake).ensure_user("bob@example.com")
    assert created.created and "could not send" in created.warning


def test_a_delivered_mail_leaves_no_warning():
    assert keycloak(FakeKeycloak()).ensure_user("bob@example.com").warning is None


def test_keycloak_actions_can_be_turned_off():
    fake = FakeKeycloak()
    keycloak(fake, send_actions=False).ensure_user("bob@example.com")
    assert not any(path.endswith("execute-actions-email") for _, path in fake.requests)


def test_the_keycloak_token_is_fetched_again_when_it_expires():
    fake = FakeKeycloak()
    now = [1000.0]
    adapter = keycloak(fake, clock=lambda: now[0])
    adapter.find_user("a@example.com")
    now[0] += 100
    adapter.find_user("a@example.com")
    assert fake.token_requests == 1
    now[0] += 400
    adapter.find_user("a@example.com")
    assert fake.token_requests == 2


def test_a_refused_admin_client_is_a_provisioning_error():
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized_client"})

    transport = httpx.MockTransport(refuse)
    token = ClientCredentialsToken(
        "https://id.example.com/token",
        "c",
        "s",
        client=httpx.Client(transport=transport),
    )
    adapter = ProvisioningKeycloak(
        "kc",
        AdminHttp(
            "https://id.example.com",
            headers=token.headers,
            client=httpx.Client(transport=transport),
        ),
        "acme",
    )
    with pytest.raises(ProvisioningError):
        adapter.ensure_user("bob@example.com")


def test_an_unreachable_admin_api_is_a_provider_unavailable():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    http = AdminHttp(
        "https://id.example.com",
        client=httpx.Client(transport=httpx.MockTransport(down)),
    )
    with pytest.raises(ProviderUnavailableError):
        ProvisioningKeycloak("kc", http, "acme").find_user("bob@example.com")


def test_a_server_error_is_a_provider_unavailable():
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    http = AdminHttp(
        "https://id.example.com",
        client=httpx.Client(transport=httpx.MockTransport(broken)),
    )
    with pytest.raises(ProviderUnavailableError):
        ProvisioningKeycloak("kc", http, "acme").find_user("bob@example.com")


def test_an_admin_path_cannot_name_another_host():
    hosts: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(200)

    http = AdminHttp(
        "https://id.example.com",
        client=httpx.Client(transport=httpx.MockTransport(record)),
    )
    with pytest.raises(ValueError):
        http.request("GET", "https://evil.example.com/x")
    http.request("GET", "//evil.example.com/x")  # a path of the base host
    assert hosts == ["id.example.com"]


# -- configuration ------------------------------------------------------------------------


def provider(**fields: Any) -> dict[str, Any]:
    return {
        "name": "acme",
        "issuer": "https://acme.example.com/realms/acme",
        "client_id": "abi",
        **fields,
    }


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"provisioning": "zitadel"}, "admin.token"),
        ({"provisioning": "zitadel", "admin": {"client_id": "x"}}, "admin.token"),
        ({"provisioning": "keycloak"}, "admin.client_id"),
        (
            {"provisioning": "keycloak", "admin": {"client_id": "x"}},
            "admin.client_secret",
        ),
        ({"provisioning": "none", "admin": {"token": "x"}}, "needs none"),
        (
            {
                "provisioning": "zitadel",
                "admin": {"token": "x", "url": "http://evil.example.com"},
            },
            "https",
        ),
    ],
)
def test_the_admin_settings_are_validated(fields, message):
    with pytest.raises(ValueError, match=message):
        IdentityConfiguration.model_validate({"providers": [provider(**fields)]})


def test_each_provisioning_setting_gets_its_adapter(iam):
    configuration = IdentityConfiguration.model_validate(
        {
            "providers": [
                provider(name="okta", issuer="https://okta.example.com"),
                provider(
                    name="zit",
                    issuer="https://zit.example.com",
                    provisioning="zitadel",
                    admin={"token": "pat", "org_id": "42"},
                ),
                provider(
                    provisioning="keycloak",
                    admin={"client_id": "abi-admin", "client_secret": "s"},
                ),
                provider(
                    name="builtin",
                    issuer="https://abi.example.com/idp",
                    provisioning="builtin",
                ),
            ]
        }
    )
    service = configuration.load(iam)
    kinds = {n: type(a).__name__ for n, a in service._provisioning.items()}
    assert kinds == {
        "okta": "ProvisioningNone",
        "zit": "ProvisioningZitadel",
        "acme": "ProvisioningKeycloak",
        "builtin": "ProvisioningBuiltinIdP",
    }


# -- claiming at the first sign-in -----------------------------------------------------------


@pytest.fixture
def idp():
    with FakeIdP() as provider_:
        yield provider_


def test_the_first_sign_in_claims_what_the_invitation_granted(idp, iam):
    service = identity_service(idp, iam)
    email = address()
    with as_service_account("engine"):
        iam.create_pending_grant(idp.provider_name, email, roles.MEMBER, W1)
        iam.create_pending_grant("another-provider", email, roles.VIEWER, W1)
    signed = sign_in(service, idp, idp.create_user(email))
    attached = {
        (a.policy_id, a.scope)
        for a in iam.store.list_attachments(principal_id=signed.user.principal_id)
    }
    assert (roles.MEMBER, W1) in attached and (roles.VIEWER, W1) not in attached
    with as_service_account("engine"):
        left = iam.list_pending_grants()
    assert [(g.provider, g.policy_id) for g in left] == [
        ("another-provider", roles.VIEWER)
    ]


def test_a_sign_in_with_an_unverified_email_claims_nothing(idp, iam):
    service = identity_service(idp, iam)
    email = address()
    with as_service_account("engine"):
        iam.create_pending_grant(idp.provider_name, email, roles.MEMBER, W1)
    user = idp.create_user(email)
    idp._users[user.subject].email_verified = False
    signed = sign_in(service, idp, user)
    assert not [
        a
        for a in iam.store.list_attachments(principal_id=signed.user.principal_id)
        if a.policy_id == roles.MEMBER
    ]
    with as_service_account("engine"):
        assert len(iam.list_pending_grants()) == 1
    # The same person, once the provider vouches for the address.
    idp._users[user.subject].email_verified = True
    signed = sign_in(service, idp, user)
    assert any(
        a.policy_id == roles.MEMBER
        for a in iam.store.list_attachments(principal_id=signed.user.principal_id)
    )


def test_an_error_while_claiming_does_not_fail_a_valid_sign_in(idp, iam, monkeypatch):
    service = identity_service(idp, iam)

    def broken(principal_id):
        raise RuntimeError("a conflict with a manual attach")

    monkeypatch.setattr(iam, "claim_pending_grants", broken)
    signed = sign_in(service, idp, idp.create_user(address()))
    assert signed.user.principal_id
