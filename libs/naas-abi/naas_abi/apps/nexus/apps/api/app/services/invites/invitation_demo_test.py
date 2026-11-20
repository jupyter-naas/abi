"""The invitation demo, end to end, with the built-in IdP and the local email adapter.

1. An admin invites ``bob@example.com`` as a member of workspace W.
2. The built-in IdP creates Bob (the provisioning port, through its admin app), and
   Nexus makes his user, ``invited``, holding the roles he was given.
3. The test reads Bob's sign-in code from the local email adapter.
4. Bob signs in: his user is ``active``.
5. Bob is a member of W: in Nexus, and in IAM.

Nexus's migrations on SQLite, its request middleware and routers, the engine's
identity service and IAM, the built-in IdP over real HTTP, and the filesystem
email adapter (what ``abi dev up`` mails through, ``storage/email/``).
"""

from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.models import (
    InvitationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (  # noqa: E501
    router as auth_router,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
)
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime as invites_runtime
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.primary.invites__primary_adapter__FastAPI import (  # noqa: E501
    idp_groups_router,
    invitations_router,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.mailer import (
    EngineInvitationMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc import runtime as oidc_runtime
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.primary.oidc__primary_adapter__FastAPI import (  # noqa: E501
    router as oidc_router,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary.organizations__primary_adapter__FastAPI import (  # noqa: E501
    router as organizations_router,
)
from naas_abi.apps.nexus.apps.api.app.services.people import runtime as people_runtime
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.mailer import (
    EnginePeopleMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.workspaces__primary_adapter__FastAPI import (  # noqa: E501
    router as workspaces_router,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
    FilesystemAdapter,
)
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.iam import roles
from naas_abi_core.services.identity.adapters.secondary.OIDCHttpHttpx import (
    OIDCHttpHttpx,
)
from naas_abi_core.services.identity.adapters.secondary.ProvisioningBuiltinIdP import (
    ProvisioningBuiltinIdP,
)
from naas_abi_core.services.identity.IdentityPorts import IdentityProvider
from naas_abi_core.services.identity.IdentityService import IdentityService
from naas_abi_core.services.identity.tests.builtin_idp_server import (
    AdminApp,
    BuiltinIdPHarness,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytest.importorskip("naas_abi_idp")

API = "https://testserver"
WEB = "https://web.test"
CALLBACK = f"{API}/api/auth/oidc/callback"
ORG, WS = "org-1", "ws-1"
CODE_DIGITS = re.compile(r"(?<![\d@.])(\d{8})(?!\d)")


class LocalEmail:
    """The IdP's ``Mailer`` over the engine's email service on the filesystem
    adapter, and a reader of what it kept: the way ``abi dev up`` mails."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.service = EmailService(FilesystemAdapter(directory=str(directory)))

    def send(self, mail) -> None:
        with as_service_account("engine"):
            self.service.send(
                to_email=mail.to,
                subject=mail.subject,
                text_body=mail.text,
                html_body=mail.html,
                from_email=mail.from_email or "idp@abi.test",
                from_name=mail.from_name,
            )

    def kept(self, to: str) -> list[tuple[str, str]]:
        """``(subject, text)`` of the mail kept for ``to``, oldest first."""
        found = []
        for path in sorted(self.directory.glob("*.eml")):
            message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            if to in str(message["To"]):
                body = message.get_body(preferencelist=("plain",))
                found.append((str(message["Subject"]), body.get_content() if body else ""))
        return found

    def last_code(self, to: str, length: int = 6) -> str:
        for subject, text in reversed(self.kept(to)):
            code = CODE_DIGITS.search(text) or CODE_DIGITS.search(subject)
            if code:
                return code.group(1)
        raise LookupError(f"no sign-in code was mailed to {to}")


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(oidc_router, prefix="/api/auth/oidc")
    app.include_router(organizations_router, prefix="/api/organizations")
    app.include_router(workspaces_router, prefix="/api/workspaces")
    app.include_router(invitations_router, prefix="/api/invitations")
    app.include_router(idp_groups_router, prefix="/api/idp-groups")
    app.add_middleware(RequestIdentityMiddleware)
    # The drive profile sync (best effort) has no object storage here.
    app.dependency_overrides[org_api._get_object_storage] = lambda: object()
    return app


@pytest.fixture
def mail(tmp_path):
    return LocalEmail(tmp_path / "email")


@pytest.fixture
def idp(mail):
    with BuiltinIdPHarness(redirect_uri=CALLBACK, mailer=mail) as harness:
        yield harness


@pytest.fixture
def provisioning() -> str:
    """The provider's ``provisioning`` setting; tests override it."""
    return "builtin"


@pytest_asyncio.fixture
async def nexus(idp, mail, tmp_path, monkeypatch, provisioning):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    monkeypatch.setattr(database, "async_engine", engine)
    monkeypatch.setattr(database, "_is_sqlite", True)
    await database.init_db()
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(settings, "api_url", API)
    monkeypatch.setattr(settings, "frontend_url", WEB)
    monkeypatch.setattr(settings, "oidc_redirect_uri", None)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    # Roles are IAM's: the same IAM Nexus asks is the one the engine claims
    # invitations into.
    world = NexusIam()
    world.org(ORG)
    world.workspace(ORG, WS)
    iam = world.iam
    installed = world.installed()
    installed.__enter__()
    admin = ProvisioningBuiltinIdP("builtin")
    admin.attach(AdminApp(idp.service))
    identity = IdentityService(
        [
            IdentityProvider(
                name="builtin",
                issuer=idp.issuer,
                client_id=idp.client_id,
                client_secret=idp.client_secret,
                groups_claim="groups",
                scopes=idp.scopes,
                provisioning=provisioning,  # type: ignore[arg-type]
            )
        ],
        iam,
        OIDCHttpHttpx(),
        default_provider="builtin",
        refetch_seconds=0.0,
        provisioning={"builtin": admin} if provisioning == "builtin" else {},
    )
    sign_in = oidc_runtime.OidcRuntime(lambda: identity, lambda: iam)
    sign_in.principals._cache_seconds = 0
    previous_sign_in = oidc_runtime.configure(sign_in)
    previous_invites = invites_runtime.configure(
        invites_runtime.InvitationRuntime(
            lambda: identity, lambda: iam, EngineInvitationMailer(lambda: mail.service)
        )
    )
    # The member invites create or link through the people service, on the same
    # identity service, IAM and mail.
    previous_people = people_runtime.configure(
        people_runtime.PeopleRuntime(
            lambda: identity,
            lambda: iam,
            mailer=EnginePeopleMailer(
                sign_in_url=invites_runtime.sign_in_url, email=lambda: mail.service
            ),
        )
    )
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url=API, follow_redirects=False
    )
    try:
        yield client, iam, sessions
    finally:
        await client.aclose()
        installed.__exit__(None, None, None)
        oidc_runtime.configure(previous_sign_in)
        invites_runtime.configure(previous_invites)
        people_runtime.configure(previous_people)
        await engine.dispose()


async def sign_in(idp, user) -> httpx.AsyncClient:
    """A browser that signed in through the IdP: its cookie and CSRF token."""
    browser = httpx.AsyncClient(transport=nexus_transport(), base_url=API, follow_redirects=False)
    started = await browser.get(
        "/api/auth/oidc/login", params={"provider": "builtin", "next": "/workspace/ws-1"}
    )
    assert started.status_code == 302, started.text
    callback = idp.sign_in(started.headers["location"], user)
    assert callback.startswith(CALLBACK)
    landed = await browser.get(callback)
    assert landed.status_code == 302 and "sso_error" not in landed.headers["location"]
    session = (await browser.get("/api/auth/oidc/session")).json()
    browser.headers["X-CSRF-Token"] = session["csrf_token"]
    return browser


_TRANSPORT: list = []


def nexus_transport():
    return _TRANSPORT[0]


def allow_provisioning(iam, principal_id: str) -> None:
    with as_service_account("engine"):
        policy = iam.create_policy(
            f"provision-{principal_id}",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["identity:ProvisionUser", "identity:FindProvisionedUser"],
                        "resources": ["abi:identity:provider/*"],
                    }
                ],
            },
        )
        iam.attach_policy(policy.id, principal_id)


@pytest_asyncio.fixture
async def alice(nexus, idp):
    """An organization owner and workspace owner of W, signed in."""
    client, _, sessions = nexus
    _TRANSPORT[:] = [client._transport]
    user = idp.create_user("alice@example.com")
    browser = await sign_in(idp, user)
    me = (await browser.get("/api/auth/me")).json()
    async with sessions() as db:
        db.add(OrganizationModel(id=ORG, name="Acme", slug="acme", owner_id=me["id"]))
        await db.flush()
        db.add(
            WorkspaceModel(
                id=WS, name="Research", slug="research", owner_id=me["id"], organization_id=ORG
            )
        )
        await db.flush()
        await db.commit()
    await MEMBERSHIPS.grant(me["id"], "owner", org_container(ORG))
    await MEMBERSHIPS.grant(me["id"], "owner", workspace_container(ORG, WS))
    # Making accounts in the provider's directory is a right of its own that
    # platform operators give (an organization's owner does not hold it).
    _, iam, _ = nexus
    allow_provisioning(iam, me["id"])
    return browser


@pytest.mark.asyncio
async def test_the_rfc_demo_invite_bob_and_he_signs_in_a_member_of_w(nexus, idp, mail, alice):
    _, iam, sessions = nexus

    # 1. An admin invites bob@example.com as a member of W.
    invited = await alice.post(
        f"/api/organizations/{ORG}/members/invite",
        json={
            "email": "Bob@Example.com",
            "role": "member",
            "workspace_id": WS,
            "workspace_role": "member",
            "job_title": "CTO",
        },
    )
    assert invited.status_code == 200, invited.text
    result = invited.json()
    assert result["status"] == "added" and result["provider"]["name"] == "builtin"
    assert result["provider"]["managed_in_provider"] is False
    assert result["sign_in_email_sent"] is True and result["warning"] is None
    # The answer never says whether the account was made or found.
    assert "user_created" not in result and "invitation" not in result
    user = result["user"]
    assert (user["email"], user["status"]) == ("bob@example.com", "invited")
    assert (result["member"]["role"], result["member"]["status"]) == ("member", "invited")

    # 2. The IdP created Bob, and Nexus made his user: invited, holding his roles.
    created = idp.service.find_user("bob@example.com")
    assert created is not None and created.id.startswith("u_")
    async with sessions() as db:
        row = (
            await db.execute(select(UserModel).where(UserModel.email == "bob@example.com"))
        ).scalar_one()
        assert (row.id, row.status, row.idp_subject) == (user["id"], "invited", created.id)
        # No invitation row: the user is the invitation.
        assert (await db.execute(select(InvitationModel))).first() is None
    assert await MEMBERSHIPS.roles_of(user["id"]) == {
        org_container(ORG): "member",
        workspace_container(ORG, WS): "member",
    }
    with as_service_account("engine"):
        # The roles are attached, not pending: nothing waits to be claimed.
        assert iam.list_pending_grants(email="bob@example.com") == []
    # Bob is listed as an invited member before he ever signs in.
    listed = (await alice.get(f"/api/organizations/{ORG}/members")).json()
    assert [
        (m["email"], m["role"], m["source"], m["status"])
        for m in listed
        if m["email"] == "bob@example.com"
    ] == [("bob@example.com", "member", "organization", "invited")]
    # Bob was told, and the invitation holds no code: the IdP mails that on sign-in.
    ((subject, text),) = mail.kept("bob@example.com")
    # The subject names the platform; the workspace and the inviter are in the body.
    assert "Research" not in subject and "Research" in text and "Alice" in text
    assert f"{WEB}/auth/login?" in text and not CODE_DIGITS.search(text)

    # 3. Bob asks for a code; the test reads it from the local email adapter.
    # 4. Bob signs in.
    bob_user = idp.service.find_user("bob@example.com")
    from naas_abi_core.services.identity.tests.identity_contract import TestUser

    bob = await sign_in(
        idp, TestUser(subject=bob_user.id, email=bob_user.email, login=bob_user.email)
    )
    codes = [s for s, _ in mail.kept("bob@example.com")]
    assert len(codes) == 2  # the invitation, then the sign-in code

    # 5. Bob is a member of W, in Nexus and in IAM, under the user made for him.
    me = (await bob.get("/api/auth/me")).json()
    assert (me["id"], me["email"]) == (user["id"], "bob@example.com")
    async with sessions() as db:
        row = (await db.execute(select(UserModel).where(UserModel.id == me["id"]))).scalar_one()
        assert row.status == "active" and row.activated_at is not None
    assert await MEMBERSHIPS.role_at(me["id"], workspace_container(ORG, WS)) == "member"
    assert await MEMBERSHIPS.role_at(me["id"], org_container(ORG)) == "member"
    # What the admin set about Bob when inviting him is his profile in the organization.
    details = (await alice.get(f"/api/organizations/{ORG}/members/{me['id']}")).json()
    assert details["organization_profile"]["job_title"] == "CTO"
    assert details["member"]["status"] == "active"
    attached = {(a.policy_id, a.scope) for a in iam.store.list_attachments(principal_id=me["id"])}
    assert {
        (roles.MEMBER, f"abi:nexus:organization/{ORG}/nexus:workspace/{WS}"),
        (roles.MEMBER, f"abi:nexus:organization/{ORG}"),
    } <= attached
    with as_service_account("engine"):
        assert iam.list_pending_grants() == []
    organizations = (await bob.get("/api/organizations")).json()
    assert [o["id"] for o in organizations] == [ORG]
    assert (await alice.get(f"/api/invitations/workspaces/{WS}")).json()["invitations"] == []


# -- the other cases -------------------------------------------------------------------


async def invite_bob(alice, **extra):
    return await alice.post(
        f"/api/organizations/{ORG}/members/invite",
        json={
            "email": "bob@example.com",
            "role": "member",
            "workspace_id": WS,
            "workspace_role": "member",
            **extra,
        },
    )


async def sign_in_as(idp, email: str):
    from naas_abi_core.services.identity.tests.identity_contract import TestUser

    found = idp.service.find_user(email)
    return await sign_in(idp, TestUser(subject=found.id, email=email, login=email))


async def user_of(sessions, email: str) -> UserModel | None:
    async with sessions() as db:
        return (
            await db.execute(select(UserModel).where(UserModel.email == email))
        ).scalar_one_or_none()


class TestProviderManagedInTheProvider:
    """``provisioning: none``: no account is made at the provider. The user is
    made ``invited`` and unbound, holding the roles, and the first verified sign-in
    through that provider binds it."""

    @pytest.fixture
    def provisioning(self) -> str:
        return "none"

    @pytest.mark.asyncio
    async def test_the_idp_is_not_asked_to_create_anyone(self, nexus, idp, mail, alice):
        _, iam, sessions = nexus
        providers = (await alice.get("/api/invitations/providers")).json()
        assert providers["enabled"] is True
        assert providers["providers"] == [
            {
                "name": "builtin",
                "display_name": "builtin",
                "provisioning": "none",
                "managed_in_provider": True,
            }
        ]
        result = (await invite_bob(alice)).json()
        assert result["status"] == "added" and result["user"]["status"] == "invited"
        assert result["provider"]["managed_in_provider"] is True
        assert "user_created" not in result
        assert idp.service.find_user("bob@example.com") is None
        row = await user_of(sessions, "bob@example.com")
        assert row is not None and row.status == "invited" and row.idp_subject is None
        assert await MEMBERSHIPS.roles_of(row.id) == {
            org_container(ORG): "member",
            workspace_container(ORG, WS): "member",
        }
        with as_service_account("engine"):
            assert iam.list_pending_grants(email="bob@example.com") == []
        ((_, text),) = mail.kept("bob@example.com")
        assert "managed" in text

    @pytest.mark.asyncio
    async def test_the_person_the_provider_made_claims_it_at_their_first_sign_in(
        self, nexus, idp, alice
    ):
        _, iam, sessions = nexus
        invited = (await invite_bob(alice)).json()["user"]
        idp.create_user("bob@example.com")  # made in the provider, not from ABI
        bob = await sign_in_as(idp, "bob@example.com")
        me = (await bob.get("/api/auth/me")).json()
        # The user made at the invitation is bound, not duplicated: same id, active.
        assert me["id"] == invited["id"]
        row = await user_of(sessions, "bob@example.com")
        assert row is not None and row.status == "active" and row.idp_subject is not None
        assert [o["id"] for o in (await bob.get("/api/organizations")).json()] == [ORG]
        assert await MEMBERSHIPS.role_at(me["id"], workspace_container(ORG, WS)) == "member"


@pytest.mark.asyncio
async def test_only_admins_invite_resend_and_remove(nexus, idp, alice):
    _, _, sessions = nexus
    bob = (await invite_bob(alice)).json()["user"]
    # A member of the organization, signed in.
    carol_user = idp.create_user("carol@example.com")
    carol = await sign_in(idp, carol_user)
    me = (await carol.get("/api/auth/me")).json()
    await MEMBERSHIPS.grant(me["id"], "member", org_container(ORG))
    await MEMBERSHIPS.grant(me["id"], "member", workspace_container(ORG, WS))
    assert (await invite_bob(carol, email="dave@example.com")).status_code == 403
    assert (
        await carol.post(
            f"/api/workspaces/{WS}/members/invite",
            json={"email": "dave@example.com", "role": "viewer"},
        )
    ).status_code == 403
    for method, path, body in (
        ("GET", f"/api/organizations/{ORG}/members", None),
        ("GET", f"/api/workspaces/{WS}/members/candidates?q=bob", None),
        ("POST", f"/api/workspaces/{WS}/members", {"user_id": bob["id"], "role": "viewer"}),
        ("POST", f"/api/organizations/{ORG}/members/{bob['id']}/resend", None),
        ("POST", f"/api/workspaces/{WS}/members/{bob['id']}/resend", None),
        ("DELETE", f"/api/organizations/{ORG}/members/{bob['id']}", None),
        ("DELETE", f"/api/workspaces/{WS}/members/{bob['id']}", None),
        ("GET", f"/api/invitations/organizations/{ORG}", None),
        ("GET", f"/api/invitations/workspaces/{WS}", None),
        ("GET", f"/api/idp-groups/organizations/{ORG}", None),
        (
            "PUT",
            f"/api/idp-groups/workspaces/{WS}",
            {"provider": "builtin", "group": "g", "role": "viewer"},
        ),
    ):
        refused = await carol.request(method, path, json=body)
        assert refused.status_code == 403, (method, path, refused.text)
    # Nothing changed: Bob holds what he was given, Dave was never made.
    assert await MEMBERSHIPS.roles_of(bob["id"]) == {
        org_container(ORG): "member",
        workspace_container(ORG, WS): "member",
    }
    assert await user_of(sessions, "dave@example.com") is None
    assert idp.service.find_user("dave@example.com") is None


@pytest.mark.asyncio
async def test_an_invitee_removed_signs_in_to_nothing(nexus, idp, mail, alice):
    _, iam, sessions = nexus
    bob = (await invite_bob(alice)).json()["user"]
    resent = await alice.post(f"/api/organizations/{ORG}/members/{bob['id']}/resend")
    assert resent.json() == {"sign_in_email_sent": True}
    assert len(mail.kept("bob@example.com")) == 2
    assert (await alice.delete(f"/api/workspaces/{WS}/members/{bob['id']}")).status_code == 200
    assert (await alice.delete(f"/api/organizations/{ORG}/members/{bob['id']}")).status_code == 200
    assert await MEMBERSHIPS.roles_of(bob["id"]) == {}
    assert (await alice.delete(f"/api/organizations/{ORG}/members/{bob['id']}")).status_code == 404
    # Out of the directory: no resend any more.
    assert (
        await alice.post(f"/api/organizations/{ORG}/members/{bob['id']}/resend")
    ).status_code == 404
    # He still exists at the IdP and signs in: to nothing.
    signed_in = await sign_in_as(idp, "bob@example.com")
    me = (await signed_in.get("/api/auth/me")).json()
    assert me["id"] == bob["id"]
    assert (await signed_in.get("/api/organizations")).json() == []
    assert not [a for a in iam.store.list_attachments(principal_id=me["id"]) if a.scope]


@pytest.mark.asyncio
async def test_inviting_to_a_workspace_alone(nexus, idp, alice):
    _, iam, sessions = nexus
    result = await alice.post(
        f"/api/workspaces/{WS}/members/invite", json={"email": "bob@example.com", "role": "viewer"}
    )
    assert result.status_code == 200, result.text
    answer = result.json()
    assert answer["status"] == "added" and answer["member"]["role"] == "viewer"
    # The workspace role only: a workspace admin never gives an org role, and Bob
    # is in the organization's directory through the workspace.
    assert await MEMBERSHIPS.roles_of(answer["user"]["id"]) == {
        workspace_container(ORG, WS): "viewer"
    }
    listed = (await alice.get(f"/api/organizations/{ORG}/members")).json()
    assert [
        (m["role"], m["source"], m["status"]) for m in listed if m["email"] == "bob@example.com"
    ] == [(None, "workspace", "invited")]
    bob = await sign_in_as(idp, "bob@example.com")
    me = (await bob.get("/api/auth/me")).json()
    assert await MEMBERSHIPS.roles_of(me["id"]) == {workspace_container(ORG, WS): "viewer"}
    assert (roles.VIEWER, f"abi:nexus:organization/{ORG}/nexus:workspace/{WS}") in {
        (a.policy_id, a.scope) for a in iam.store.list_attachments(principal_id=me["id"])
    }


@pytest.mark.asyncio
async def test_a_workspace_of_another_organization_is_refused(nexus, idp, alice):
    _, _, sessions = nexus
    refused = await invite_bob(alice, workspace_id="ws-elsewhere")
    assert refused.status_code == 400
    assert idp.service.find_user("bob@example.com") is None
    assert await user_of(sessions, "bob@example.com") is None


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_and_nothing_is_made(nexus, idp, alice):
    _, iam, sessions = nexus
    refused = await invite_bob(alice, provider="nope")
    assert refused.status_code == 422, refused.text
    assert idp.service.find_user("bob@example.com") is None
    assert await user_of(sessions, "bob@example.com") is None
    with as_service_account("engine"):
        assert iam.list_pending_grants() == []


@pytest.mark.asyncio
async def test_someone_who_already_has_an_account_is_linked_never_duplicated(nexus, idp, alice):
    _, _, sessions = nexus
    async with sessions() as db:
        db.add(UserModel(id="u-old", email="bob@example.com", name="Bob"))
        await db.commit()
    result = await invite_bob(alice)
    assert result.status_code == 200, result.text
    answer = result.json()
    # The same answer as a creation: only the id says who it is.
    assert answer["status"] == "added" and answer["user"]["id"] == "u-old"
    assert set(answer) == {"status", "user", "member", "provider", "sign_in_email_sent", "warning"}
    assert idp.service.find_user("bob@example.com") is None  # no provider involved
    async with sessions() as db:
        rows = (
            (await db.execute(select(UserModel).where(UserModel.email == "bob@example.com")))
            .scalars()
            .all()
        )
    assert [r.id for r in rows] == ["u-old"]
    assert await MEMBERSHIPS.roles_of("u-old") == {
        org_container(ORG): "member",
        workspace_container(ORG, WS): "member",
    }


@pytest.mark.asyncio
async def test_an_idp_group_is_bound_to_a_role_and_its_members_arrive_with_it(nexus, idp, alice):
    _, iam, _ = nexus
    listed = (await alice.get(f"/api/idp-groups/workspaces/{WS}")).json()
    assert listed["bindings"] == [] and listed["roles"] == ["admin", "member", "viewer"]
    assert [p["name"] for p in listed["providers"]] == ["builtin"]
    bound = await alice.put(
        f"/api/idp-groups/workspaces/{WS}",
        json={"provider": "builtin", "group": "Data readers", "role": "viewer"},
    )
    assert bound.status_code == 200, bound.text
    assert bound.json()["bindings"] == [
        {"provider": "builtin", "group": "Data readers", "role": "viewer"}
    ]
    # The org scope is its own list, with its own roles.
    org = (await alice.get(f"/api/idp-groups/organizations/{ORG}")).json()
    assert org["bindings"] == [] and org["roles"] == ["admin", "member"]
    refused = await alice.put(
        f"/api/idp-groups/organizations/{ORG}",
        json={"provider": "builtin", "group": "Data readers", "role": "viewer"},
    )
    assert refused.status_code == 400
    unknown = await alice.put(
        f"/api/idp-groups/workspaces/{WS}",
        json={"provider": "nope", "group": "g", "role": "viewer"},
    )
    assert unknown.status_code == 400

    # Someone in that IdP group arrives holding the group, and with it the role.
    idp.create_user("rita@example.com", groups=["Data readers"])
    rita = await sign_in_as(idp, "rita@example.com")
    session = (await rita.get("/api/auth/oidc/session")).json()
    me = session["user"]
    groups = iam.store.resolve_idp_groups("builtin", ["Data readers"])
    assert len(groups) == 1
    held = {
        (a.policy_id, a.scope)
        for a in iam.store.list_attachments(principal_id=groups[0])
        if a.scope
    }
    # (IAM's feature companions of a role are not part of what the binding holds.)
    held = {(p, sc) for p, sc in held if not p.startswith("builtin.features.")}
    assert held == {(roles.VIEWER, f"abi:nexus:organization/{ORG}/nexus:workspace/{WS}")}
    assert me["email"] == "rita@example.com"

    removed = await alice.delete(
        f"/api/idp-groups/workspaces/{WS}",
        params={"provider": "builtin", "group": "Data readers", "role": "viewer"},
    )
    assert removed.json()["bindings"] == []
    assert not [a for a in iam.store.list_attachments(principal_id=groups[0]) if a.scope]


@pytest.mark.asyncio
async def test_a_provider_that_cannot_make_the_person_leaves_nothing_behind(nexus, idp, alice):
    _, iam, sessions = nexus
    from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError

    class Down:
        def ensure_user(self, email, *, name=None):
            raise ProviderUnavailableError("The built-in identity provider is not reachable yet")

        find_user = ensure_user

    identity = invites_runtime.RUNTIME.directory._identity()
    identity._provisioning["builtin"] = Down()
    failed = await invite_bob(alice)
    assert failed.status_code == 502, failed.text
    assert "could not create the user" in failed.json()["detail"]
    with as_service_account("engine"):
        assert iam.list_pending_grants() == []
    assert await user_of(sessions, "bob@example.com") is None
    listed = (await alice.get(f"/api/organizations/{ORG}/members")).json()
    assert "bob@example.com" not in {m["email"] for m in listed}


@pytest.mark.asyncio
async def test_an_admin_cannot_invite_an_owner_but_an_owner_can(nexus, idp, alice):
    _, iam, sessions = nexus
    carol_user = idp.create_user("carol@example.com")
    carol = await sign_in(idp, carol_user)
    me = (await carol.get("/api/auth/me")).json()
    await MEMBERSHIPS.grant(me["id"], "admin", org_container(ORG))
    refused = await carol.post(
        f"/api/organizations/{ORG}/members/invite",
        json={"email": "dave@example.com", "role": "owner"},
    )
    assert refused.status_code == 403, refused.text
    assert idp.service.find_user("dave@example.com") is None
    assert await user_of(sessions, "dave@example.com") is None
    with as_service_account("engine"):
        assert iam.list_pending_grants() == []
    # An admin still invites members and admins; an owner invites an owner.
    admin = await carol.post(
        f"/api/organizations/{ORG}/members/invite",
        json={"email": "erin@example.com", "role": "admin"},
    )
    assert admin.status_code == 200, admin.text
    assert await MEMBERSHIPS.role_at(admin.json()["user"]["id"], org_container(ORG)) == "admin"
    granted = await alice.post(
        f"/api/organizations/{ORG}/members/invite",
        json={"email": "dave@example.com", "role": "owner"},
    )
    assert granted.status_code == 200, granted.text
    assert await MEMBERSHIPS.role_at(granted.json()["user"]["id"], org_container(ORG)) == "owner"


@pytest.mark.asyncio
async def test_an_invitee_in_two_workspaces_keeps_one_when_removed_from_the_other(
    nexus, idp, alice
):
    _, iam, sessions = nexus
    async with sessions() as db:
        owner = (
            await db.execute(select(UserModel.id).where(UserModel.email == "alice@example.com"))
        ).scalar_one()
        db.add(
            WorkspaceModel(id="ws-2", name="Ops", slug="ops", owner_id=owner, organization_id=ORG)
        )
        await db.commit()
    await MEMBERSHIPS.register_workspace(ORG, "ws-2")
    bob = (await invite_bob(alice)).json()["user"]
    # The second workspace links the user the first invitation made.
    second = await alice.post(
        "/api/workspaces/ws-2/members/invite", json={"email": "bob@example.com", "role": "member"}
    )
    assert second.status_code == 200, second.text
    assert second.json()["user"]["id"] == bob["id"]
    assert (await alice.delete(f"/api/workspaces/{WS}/members/{bob['id']}")).status_code == 200
    assert await MEMBERSHIPS.roles_of(bob["id"]) == {
        org_container(ORG): "member",
        workspace_container(ORG, "ws-2"): "member",
    }
    assert (await alice.delete(f"/api/workspaces/ws-2/members/{bob['id']}")).status_code == 200
    assert await MEMBERSHIPS.roles_of(bob["id"]) == {org_container(ORG): "member"}
    with as_service_account("engine"):
        assert iam.list_pending_grants() == []


@pytest.mark.asyncio
async def test_unbinding_answers_like_binding(nexus, idp, alice):
    path = f"/api/idp-groups/workspaces/{WS}"
    params = {"provider": "builtin", "group": "eng", "role": "viewer"}
    # Not bound: 404. A role that cannot be bound here, or an unknown provider: 400.
    assert (await alice.delete(path, params=params)).status_code == 404
    assert (await alice.delete(path, params={**params, "role": "owner"})).status_code == 400
    assert (await alice.delete(path, params={**params, "provider": "Bad Name"})).status_code == 400
    assert (await alice.delete(path, params={**params, "provider": "nope"})).status_code == 404
    bound = await alice.put(path, json={"provider": "builtin", "group": "eng", "role": "viewer"})
    assert bound.status_code == 200
    assert (await alice.delete(path, params=params)).json()["bindings"] == []
    assert (
        await alice.delete(
            f"/api/idp-groups/organizations/{ORG}", params={**params, "role": "viewer"}
        )
    ).status_code == 400


# -- who may make accounts in the provider's directory ---------------------------------


async def _carol_with_her_own_org(idp, sessions):
    """Any signed-in user may create an organization; she owns it."""
    carol = await sign_in(idp, idp.create_user("carol@example.com"))
    made = await carol.post("/api/organizations", json={"name": "Carol Co", "slug": "carol-co"})
    assert made.status_code == 200, made.text
    return carol, made.json()["id"]


async def _invite(carol, org_id: str, email: str):
    return await carol.post(
        f"/api/organizations/{org_id}/members/invite", json={"email": email, "role": "member"}
    )


@pytest.mark.asyncio
async def test_an_organization_admins_invitation_makes_an_account_they_sign_in_with(
    nexus, idp, mail, alice
):
    """Carol owns her organization and holds no ``identity:ProvisionUser``. The
    invitation IAM authorized makes the account all the same (as Nexus): with the
    provider's self-signup off, as here, the person could otherwise never get a code
    (#1520)."""
    _, iam, sessions = nexus
    carol, org_id = await _carol_with_her_own_org(idp, None)
    sent = await _invite(carol, org_id, "dana@corp.example")
    assert sent.status_code == 200, sent.text
    result = sent.json()
    assert result["status"] == "added" and result["user"]["status"] == "invited"
    assert "user_created" not in result and "provisioning_skipped" not in result
    assert idp.service.find_user("dana@corp.example") is not None
    ((_, text),) = mail.kept("dana@corp.example")
    assert "sign-in code" in text
    # Dana asks for a code, gets it and signs in, a member of Carol's organization.
    dana = await sign_in_as(idp, "dana@corp.example")
    me = (await dana.get("/api/auth/me")).json()
    assert me["id"] == result["user"]["id"]
    assert await MEMBERSHIPS.role_at(me["id"], org_container(org_id)) == "member"
    with as_service_account("engine"):
        assert iam.list_pending_grants(email="dana@corp.example") == []


@pytest.mark.asyncio
async def test_a_workspace_owners_invitation_makes_the_account(nexus, idp, alice):
    _, _, sessions = nexus
    owner = await sign_in(idp, idp.create_user("wowner@example.com"))
    me = (await owner.get("/api/auth/me")).json()
    await MEMBERSHIPS.grant(me["id"], "owner", workspace_container(ORG, WS))
    sent = await owner.post(
        f"/api/workspaces/{WS}/members/invite", json={"email": "erin@example.com", "role": "member"}
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "added" and "user_created" not in sent.json()
    assert idp.service.find_user("erin@example.com") is not None
    row = await user_of(sessions, "erin@example.com")
    assert row is not None and row.status == "invited"
    assert await MEMBERSHIPS.roles_of(row.id) == {workspace_container(ORG, WS): "member"}


@pytest.mark.asyncio
async def test_an_invitation_iam_refuses_makes_no_account(nexus, idp, alice):
    """The authorized invitation is the warrant, and nothing else: Carol may not
    invite to an organization she has no role in, nor a viewer to their workspace."""
    _, iam, _ = nexus
    carol, _ = await _carol_with_her_own_org(idp, None)
    refused = await _invite(carol, ORG, "victim@corp.example")
    assert refused.status_code == 403, refused.text
    viewer = await sign_in(idp, idp.create_user("viewer@example.com"))
    me = (await viewer.get("/api/auth/me")).json()
    await MEMBERSHIPS.grant(me["id"], "viewer", workspace_container(ORG, WS))
    also = await viewer.post(
        f"/api/workspaces/{WS}/members/invite",
        json={"email": "victim@corp.example", "role": "viewer"},
    )
    assert also.status_code == 403, also.text
    assert idp.service.find_user("victim@corp.example") is None
    with as_service_account("engine"):
        assert iam.list_pending_grants(email="victim@corp.example") == []


# -- invitations that carry an organization role ---------------------------------------


async def _workspace_admin(idp, email="wadmin@example.com"):
    user = await sign_in(idp, idp.create_user(email))
    me = (await user.get("/api/auth/me")).json()
    await MEMBERSHIPS.grant(me["id"], "admin", workspace_container(ORG, WS))
    return user


@pytest.mark.asyncio
async def test_a_workspace_admin_cannot_touch_an_invitees_org_role(nexus, idp, alice):
    _, iam, _ = nexus
    bob = (await invite_bob(alice)).json()["user"]  # org role + workspace role
    wadmin = await _workspace_admin(idp)
    assert (
        await wadmin.post(f"/api/organizations/{ORG}/members/{bob['id']}/resend")
    ).status_code == 403
    assert (await wadmin.delete(f"/api/organizations/{ORG}/members/{bob['id']}")).status_code == 403
    assert (
        await wadmin.patch(f"/api/organizations/{ORG}/members/{bob['id']}", json={"role": "admin"})
    ).status_code == 403
    assert await MEMBERSHIPS.role_at(bob["id"], org_container(ORG)) == "member"
    # Bob is a member of their workspace: they may send him his sign-in mail again.
    resent = await wadmin.post(f"/api/workspaces/{WS}/members/{bob['id']}/resend")
    assert resent.status_code == 200, resent.text
    # The organization's admin may resend, and remove the org role.
    assert (
        await alice.post(f"/api/organizations/{ORG}/members/{bob['id']}/resend")
    ).status_code == 200
    assert (await alice.delete(f"/api/organizations/{ORG}/members/{bob['id']}")).status_code == 200
    assert await MEMBERSHIPS.roles_of(bob["id"]) == {workspace_container(ORG, WS): "member"}


@pytest.mark.asyncio
async def test_inviting_a_member_again_is_a_conflict_that_changes_nothing(nexus, idp, alice):
    _, iam, _ = nexus
    bob = (await invite_bob(alice)).json()["user"]
    held = {org_container(ORG): "member", workspace_container(ORG, WS): "member"}
    wadmin = await _workspace_admin(idp)
    for who in (wadmin, alice):
        again = await who.post(
            f"/api/workspaces/{WS}/members/invite",
            json={"email": "bob@example.com", "role": "viewer"},
        )
        assert again.status_code == 409, again.text
        assert await MEMBERSHIPS.roles_of(bob["id"]) == held
    # A role is changed as a member's role, and the org role stays.
    changed = await alice.patch(
        f"/api/workspaces/{WS}/members/{bob['id']}", json={"role": "viewer"}
    )
    assert changed.status_code == 200, changed.text
    assert await MEMBERSHIPS.roles_of(bob["id"]) == {
        org_container(ORG): "member",
        workspace_container(ORG, WS): "viewer",
    }
    with as_service_account("engine"):
        assert iam.list_pending_grants(email="bob@example.com") == []
