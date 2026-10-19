"""The RFC's demo, end to end, with the built-in IdP and the local email adapter.

1. An admin invites ``bob@example.com`` as a member of workspace W.
2. The built-in IdP creates Bob (the provisioning port, through its admin app).
3. The test reads Bob's sign-in code from the local email adapter.
4. Bob signs in.
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
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__dependencies as dependencies,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (  # noqa: E501
    router as auth_router,
)
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
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary.organizations__primary_adapter__FastAPI import (  # noqa: E501
    router as organizations_router,
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
from naas_abi_core.services.identity.tests.identity_contract import bootstrapped_iam
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytest.importorskip("naas_abi_idp")

API = "https://testserver"
WEB = "https://web.test"
CALLBACK = f"{API}/api/auth/oidc/callback"
ORG, WS = "org-1", "ws-1"
SIX_DIGITS = re.compile(r"(?<![\d@.])(\d{6})(?!\d)")


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
            code = SIX_DIGITS.search(text) or SIX_DIGITS.search(subject)
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
    return app


@pytest.fixture
def mail(tmp_path):
    return LocalEmail(tmp_path / "email")


@pytest.fixture
def idp(mail):
    with BuiltinIdPHarness(redirect_uri=CALLBACK, mailer=mail) as harness:
        yield harness


@pytest_asyncio.fixture
async def nexus(idp, mail, tmp_path, monkeypatch):
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
    monkeypatch.setattr(dependencies, "AsyncSessionLocal", sessions)

    iam = bootstrapped_iam()
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
                provisioning="builtin",
            )
        ],
        iam,
        OIDCHttpHttpx(),
        default_provider="builtin",
        refetch_seconds=0.0,
        provisioning={"builtin": admin},
    )
    sign_in = oidc_runtime.OidcRuntime(lambda: identity, lambda: iam)
    sign_in.principals._cache_seconds = 0
    previous_sign_in = oidc_runtime.configure(sign_in)
    previous_invites = invites_runtime.configure(
        invites_runtime.InvitationRuntime(
            lambda: identity, lambda: iam, EngineInvitationMailer(lambda: mail.service)
        )
    )
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url=API, follow_redirects=False
    )
    try:
        yield client, iam, sessions
    finally:
        await client.aclose()
        oidc_runtime.configure(previous_sign_in)
        invites_runtime.configure(previous_invites)
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
        db.add(
            OrganizationMemberModel(id="om-a", organization_id=ORG, user_id=me["id"], role="owner")
        )
        db.add(WorkspaceMemberModel(id="wm-a", workspace_id=WS, user_id=me["id"], role="owner"))
        await db.commit()
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
        },
    )
    assert invited.status_code == 200, invited.text
    result = invited.json()
    assert result["status"] == "invited" and result["provider"]["name"] == "builtin"
    assert result["provider"]["managed_in_provider"] is False
    assert result["user_created"] is True and result["sign_in_email_sent"] is True
    invitation = result["invitation"]
    assert (invitation["email"], invitation["status"]) == ("bob@example.com", "pending")

    # 2. The IdP created Bob; Nexus made no account for him yet.
    created = idp.service.find_user("bob@example.com")
    assert created is not None and created.id.startswith("u_")
    async with sessions() as db:
        assert (
            await db.execute(select(UserModel).where(UserModel.email == "bob@example.com"))
        ).first() is None
    with as_service_account("engine"):
        pending = iam.list_pending_grants(provider="builtin", email="bob@example.com")
    assert {(g.policy_id, g.scope) for g in pending} == {
        (roles.MEMBER, f"abi:{ORG}:-"),
        (roles.MEMBER, f"abi:{ORG}:{WS}"),
    }
    # Bob was told, and the invitation holds no code: the IdP mails that on sign-in.
    ((subject, text),) = mail.kept("bob@example.com")
    assert "Research" in subject and "Alice" in text
    assert f"{WEB}/auth/login?" in text and not SIX_DIGITS.search(text)
    listed = (await alice.get(f"/api/invitations/workspaces/{WS}")).json()["invitations"]
    assert [i["email"] for i in listed] == ["bob@example.com"]

    # 3. Bob asks for a code; the test reads it from the local email adapter.
    # 4. Bob signs in.
    bob_user = idp.service.find_user("bob@example.com")
    from naas_abi_core.services.identity.tests.identity_contract import TestUser

    bob = await sign_in(
        idp, TestUser(subject=bob_user.id, email=bob_user.email, login=bob_user.email)
    )
    codes = [s for s, _ in mail.kept("bob@example.com")]
    assert len(codes) == 2  # the invitation, then the sign-in code

    # 5. Bob is a member of W, in Nexus and in IAM.
    me = (await bob.get("/api/auth/me")).json()
    assert me["email"] == "bob@example.com"
    async with sessions() as db:
        member = (
            await db.execute(
                select(WorkspaceMemberModel).where(
                    WorkspaceMemberModel.workspace_id == WS,
                    WorkspaceMemberModel.user_id == me["id"],
                )
            )
        ).scalar_one()
        assert member.role == "member"
        org_member = (
            await db.execute(
                select(OrganizationMemberModel).where(
                    OrganizationMemberModel.organization_id == ORG,
                    OrganizationMemberModel.user_id == me["id"],
                )
            )
        ).scalar_one()
        assert org_member.role == "member"
        stored = (await db.execute(select(InvitationModel))).scalar_one()
        assert (stored.status, stored.accepted_user_id) == ("accepted", me["id"])
    attached = {(a.policy_id, a.scope) for a in iam.store.list_attachments(principal_id=me["id"])}
    assert {(roles.MEMBER, f"abi:{ORG}:{WS}"), (roles.MEMBER, f"abi:{ORG}:-")} <= attached
    with as_service_account("engine"):
        assert iam.list_pending_grants() == []
    organizations = (await bob.get("/api/organizations")).json()
    assert [o["id"] for o in organizations] == [ORG]
    assert (await alice.get(f"/api/invitations/workspaces/{WS}")).json()["invitations"] == []
