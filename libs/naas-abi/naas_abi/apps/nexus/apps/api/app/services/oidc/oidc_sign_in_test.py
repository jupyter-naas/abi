"""Signing in to Nexus through an identity provider, end to end.

Nexus's migrations on SQLite, its request middleware, ``/api/auth`` and
``/api/auth/oidc``, the engine's identity service and IAM, and a provider over
real HTTP: the in-process ``FakeIdP`` always, Zitadel from its pinned native
binary when it is available (``ABI_REQUIRE_ZITADEL=1`` requires it).
"""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    OrganizationDomainModel,
    OrganizationModel,
    UserModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (  # noqa: E501
    router as auth_router,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
    AuthSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
    InvalidCredentialsError,
    get_password_hash,
    verify_password,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc import runtime
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.primary.oidc__primary_adapter__FastAPI import (  # noqa: E501
    BINDING_COOKIE,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.primary.oidc__primary_adapter__FastAPI import (  # noqa: E501
    router as oidc_router,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
    EngineIdentityGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.postgres import (
    OidcSessionSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.port import UserConflictError
from naas_abi_core.engine.call_context import as_service_account, current_call_context
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.identity.IdentityPorts import SignInError
from naas_abi_core.services.identity.tests.fake_idp import FakeIdP
from naas_abi_core.services.identity.tests.identity_contract import (
    bootstrapped_iam,
    identity_service,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

API = "https://testserver"
WEB = "https://web.test"
CALLBACK = f"{API}/api/auth/oidc/callback"


def datetime_now():
    from naas_abi.apps.nexus.apps.api.app.services.oidc.service import now_naive

    return now_naive()


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(oidc_router, prefix="/api/auth/oidc")

    @app.get("/api/whoami")
    async def whoami() -> dict:
        ctx = current_call_context()
        user = ctx.on_behalf_of
        return {
            "actor": ctx.principal.id,
            "user": user.id if user else None,
            "groups": sorted(user.groups) if user else [],
        }

    app.add_middleware(RequestIdentityMiddleware)
    return app


class NexusSignInContract:
    """Subclasses give a ``harness`` fixture whose redirect URI is ``CALLBACK``."""

    @pytest_asyncio.fixture
    async def nexus(self, harness, tmp_path, monkeypatch):
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
        monkeypatch.setattr(database, "async_engine", engine)
        monkeypatch.setattr(database, "_is_sqlite", True)
        await database.init_db()
        await database.init_db()  # migrations rerun at every boot
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(database, "AsyncSessionLocal", sessions)
        monkeypatch.setattr(settings, "api_url", API)
        monkeypatch.setattr(settings, "frontend_url", WEB)
        monkeypatch.setattr(settings, "oidc_redirect_uri", None)

        iam = bootstrapped_iam()
        identity = identity_service(harness, iam)
        test_runtime = runtime.OidcRuntime(lambda: identity, lambda: iam)
        test_runtime.principals._cache_seconds = 0
        previous = runtime.configure(test_runtime)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app()), base_url=API, follow_redirects=False
        )
        try:
            yield client, iam, sessions
        finally:
            await client.aclose()
            runtime.configure(previous)
            await engine.dispose()

    async def _sign_in(self, client, harness, user, *, next_path="/workspace/w1"):
        started = await client.get(
            "/api/auth/oidc/login",
            params={"provider": harness.provider_name, "next": next_path},
        )
        assert started.status_code == 302, started.text
        assert BINDING_COOKIE in started.headers.get("set-cookie", "")
        callback = harness.sign_in(started.headers["location"], user)
        assert callback.startswith(CALLBACK)
        return await client.get(callback)

    # -- the sign-in ------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_a_user_signs_in_and_becomes_an_iam_principal(self, nexus, harness):
        client, iam, sessions = nexus
        listed = (await client.get("/api/auth/oidc/providers")).json()
        assert harness.provider_name in [p["name"] for p in listed["providers"]]

        user = harness.create_user(f"ada-{os.urandom(3).hex()}@example.com")
        landed = await self._sign_in(client, harness, user)
        assert landed.status_code == 302
        assert landed.headers["location"] == f"{WEB}/auth/callback?next=%2Fworkspace%2Fw1"
        cookie = landed.headers["set-cookie"]
        for flag in ("HttpOnly", "Secure", "SameSite=lax"):
            assert flag.lower() in cookie.lower()

        me = (await client.get("/api/auth/me")).json()
        record = iam.store.find_user(harness.issuer, user.subject)
        assert record is not None and record.status == "active"
        assert me["id"] == record.id  # one Nexus row per (issuer, sub): its principal
        assert me["email"] == user.email
        async with sessions() as db:
            row = (await db.execute(select(UserModel).where(UserModel.id == me["id"]))).scalar_one()
            assert (row.principal_id, row.idp_issuer, row.idp_subject) == (
                record.id,
                harness.issuer,
                user.subject,
            )
            assert row.hashed_password == ""

        # Every kernel call runs as api on behalf of the principal.
        assert (await client.get("/api/whoami")).json()["user"] == record.id
        assert (await client.get("/api/whoami")).json()["actor"] == "api"
        # TRANSITIONAL (#65): Nexus still decides what its users may do.
        attached = [a.policy_id for a in iam.store.list_attachments(principal_id=record.id)]
        assert roles.TRANSITIONAL_NEXUS_USER in attached

    @pytest.mark.asyncio
    async def test_the_same_identity_signs_in_to_the_same_account(self, nexus, harness):
        client, _, _ = nexus
        user = harness.create_user(f"bea-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        first = (await client.get("/api/auth/me")).json()["id"]
        client.cookies.clear()
        await self._sign_in(client, harness, user)
        assert (await client.get("/api/auth/me")).json()["id"] == first

    @pytest.mark.asyncio
    async def test_changes_need_the_sessions_csrf_token(self, nexus, harness):
        client, _, _ = nexus
        user = harness.create_user(f"cy-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        refused = await client.patch("/api/auth/me", json={"name": "Mallory"})
        assert refused.status_code == 403
        session = (await client.get("/api/auth/oidc/session")).json()
        assert session["user"]["email"] == user.email
        headers = {"X-CSRF-Token": session["csrf_token"]}
        wrong = await client.patch(
            "/api/auth/me", json={"name": "Mallory"}, headers={"X-CSRF-Token": "nope"}
        )
        assert wrong.status_code == 403
        renamed = await client.patch(
            "/api/auth/me",
            json={"name": "Cy", "email": "someone-else@example.com"},
            headers=headers,
        )
        assert renamed.status_code == 200
        # The provider states the email: it is never changed in Nexus.
        assert renamed.json()["email"] == user.email

    @pytest.mark.asyncio
    async def test_the_provider_vouches_again_within_ten_minutes(self, nexus, harness):
        client, iam, sessions = nexus
        user = harness.create_user(f"dee-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        session = (await client.get("/api/auth/oidc/session")).json()
        async with sessions() as db:
            stored = (await db.execute(select(AuthSessionModel))).scalars().all()
            assert stored and all(s.refresh_token_enc for s in stored)
            # Encrypted at rest.
            assert all("." not in (s.refresh_token_enc or "")[:8] for s in stored)
            await db.execute(update(AuthSessionModel).values(refresh_at=stored[0].created_at))
            await db.commit()
        assert (await client.get("/api/auth/me")).status_code == 200
        async with sessions() as db:
            refreshed = (await db.execute(select(AuthSessionModel))).scalars().all()
            assert any(s.refresh_at > s.created_at for s in refreshed)
        assert session["refresh_at"]

    @pytest.mark.asyncio
    async def test_a_suspended_principal_is_signed_out_at_once(self, nexus, harness):
        client, iam, _ = nexus
        user = harness.create_user(f"eve-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        principal = (await client.get("/api/auth/me")).json()["id"]
        with as_service_account("engine"):
            iam.suspend_principal(principal)
        assert (await client.get("/api/auth/me")).status_code == 401
        assert (await client.get("/api/whoami")).json()["user"] is None

    @pytest.mark.asyncio
    async def test_logout_ends_the_session(self, nexus, harness):
        client, _, _ = nexus
        user = harness.create_user(f"fay-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        csrf = (await client.get("/api/auth/oidc/session")).json()["csrf_token"]
        assert (await client.post("/api/auth/oidc/logout")).status_code == 403
        cookie = client.cookies.get(settings.oidc_session_cookie)
        out = await client.post("/api/auth/oidc/logout", headers={"X-CSRF-Token": csrf})
        assert out.status_code == 200
        # The ended session stays ended, even with its cookie replayed.
        client.cookies.set(settings.oidc_session_cookie, cookie or "", domain="testserver")
        assert (await client.get("/api/auth/me")).status_code == 401

    # -- what is refused --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_a_callback_from_another_browser_is_refused(self, nexus, harness):
        client, _, _ = nexus
        user = harness.create_user(f"gus-{os.urandom(3).hex()}@example.com")
        started = await client.get(
            "/api/auth/oidc/login", params={"provider": harness.provider_name}
        )
        callback = harness.sign_in(started.headers["location"], user)
        client.cookies.clear()
        landed = await client.get(callback)
        assert landed.headers["location"] == f"{WEB}/auth/login?sso_error=browser_mismatch"
        assert (await client.get("/api/auth/me")).status_code == 401

    @pytest.mark.asyncio
    async def test_a_callback_is_used_once(self, nexus, harness):
        client, _, _ = nexus
        user = harness.create_user(f"hal-{os.urandom(3).hex()}@example.com")
        started = await client.get(
            "/api/auth/oidc/login", params={"provider": harness.provider_name}
        )
        callback = harness.sign_in(started.headers["location"], user)
        assert (await client.get(callback)).headers["location"].startswith(f"{WEB}/auth/callback")
        replayed = await client.get(callback)
        assert replayed.headers["location"] == f"{WEB}/auth/login?sso_error=expired_request"

    @pytest.mark.asyncio
    async def test_an_email_another_account_holds_is_never_linked(self, nexus, harness):
        client, _, sessions = nexus
        email = f"ivy-{os.urandom(3).hex()}@example.com"
        async with sessions() as db:
            db.add(UserModel(id="legacy-ivy", email=email, name="Ivy", hashed_password="x"))
            await db.commit()
        landed = await self._sign_in(client, harness, harness.create_user(email))
        assert landed.headers["location"] == f"{WEB}/auth/login?sso_error=email_in_use"

    @pytest.mark.asyncio
    async def test_the_built_in_login_never_opens_a_provider_account(
        self, nexus, harness, monkeypatch
    ):
        client, _, sessions = nexus
        user = harness.create_user(f"jo-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        monkeypatch.setattr(settings, "auth_password_enabled", True)
        async with sessions() as db:
            auth = AuthService(AuthSecondaryAdapterPostgres(db=db))
            with pytest.raises(InvalidCredentialsError):
                await auth.login_user(user.email, "", None, None)
            assert await auth.forgot_password(user.email) is None
            assert await auth.request_magic_link(user.email) is None

    @pytest.mark.asyncio
    async def test_an_email_domain_routes_to_its_provider(self, nexus, harness):
        client, _, sessions = nexus
        async with sessions() as db:
            db.add(
                UserModel(id="owner-1", email="owner@example.com", name="O", hashed_password="x")
            )
            db.add(OrganizationModel(id="org-1", name="Acme", slug="acme", owner_id="owner-1"))
            db.add(
                OrganizationDomainModel(
                    id="d-1",
                    organization_id="org-1",
                    domain="acme.test",
                    is_verified=True,
                    provider=harness.provider_name,
                )
            )
            db.add(
                OrganizationDomainModel(
                    id="d-2",
                    organization_id="org-1",
                    domain="unverified.test",
                    is_verified=False,
                    provider=harness.provider_name,
                )
            )
            await db.commit()
        routed = await client.post("/api/auth/oidc/route", json={"email": "a@acme.test"})
        assert routed.json() == {"provider": harness.provider_name}
        # Routing needs a verified domain.
        assert (
            await client.post("/api/auth/oidc/route", json={"email": "a@unverified.test"})
        ).json() == {"provider": None}
        started = await client.get("/api/auth/oidc/login", params={"email": "x@acme.test"})
        assert started.status_code == 302
        assert urlsplit(started.headers["location"]).netloc == urlsplit(harness.issuer).netloc
        assert parse_qs(urlsplit(started.headers["location"]).query)["login_hint"] == [
            "x@acme.test"
        ]

    @pytest.mark.asyncio
    async def test_mapped_groups_travel_with_the_user(self, nexus, harness):
        if not harness.groups_claim:
            pytest.skip("the provider sends no groups claim")
        client, iam, _ = nexus
        claim = f"editors-{os.urandom(3).hex()}"
        with as_service_account("engine"):
            group = iam.create_group("Editors")
            iam.map_idp_group(harness.provider_name, claim, group.id)
        user = harness.create_user(f"kim-{os.urandom(3).hex()}@example.com", groups=[claim])
        await self._sign_in(client, harness, user)
        assert (await client.get("/api/whoami")).json()["groups"] == [group.id]

    # -- the default provider never captures the built-in logins -----------------

    @pytest.fixture
    def with_default(self, nexus, harness):
        """The provider is also the engine's ``default_provider``."""
        identity = runtime.RUNTIME.identity._identity()
        previous, identity._default = identity._default, harness.provider_name
        yield
        identity._default = previous

    @pytest.mark.asyncio
    async def test_an_email_without_a_domain_mapping_is_not_routed_to_the_default(
        self, nexus, harness, with_default
    ):
        client, _, _ = nexus
        providers = (await client.get("/api/auth/oidc/providers")).json()
        # The login page offers it as a button...
        assert providers["default_provider"] == harness.provider_name
        # ...but no email is sent there on its own: the built-in login stays open.
        for email in ("admin@example.com", "someone@elsewhere.test"):
            routed = await client.post("/api/auth/oidc/route", json={"email": email})
            assert routed.json() == {"provider": None}
        started = await client.get("/api/auth/oidc/login", params={"email": "admin@example.com"})
        assert started.headers["location"] == f"{WEB}/auth/login?sso_error=no_provider"
        # /login with neither provider nor email is the default's button.
        bare = await client.get("/api/auth/oidc/login")
        assert urlsplit(bare.headers["location"]).netloc == urlsplit(harness.issuer).netloc

    @pytest.mark.asyncio
    async def test_a_built_in_account_is_not_sent_to_the_default_provider(
        self, nexus, harness, with_default
    ):
        client, _, sessions = nexus
        async with sessions() as db:
            db.add(
                UserModel(
                    id="usr_seeded",
                    email="admin@example.com",
                    name="Admin",
                    hashed_password=get_password_hash("Correct-horse-9"),
                )
            )
            await db.commit()
            # The built-in login still opens it (its own tests cover the rest).
            seeded = await AuthSecondaryAdapterPostgres(db=db).get_user_by_email(
                "admin@example.com"
            )
            assert seeded is not None and verify_password("Correct-horse-9", seeded.hashed_password)
        routed = await client.post("/api/auth/oidc/route", json={"email": "admin@example.com"})
        assert routed.json() == {"provider": None}  # the form goes on to the password

    # -- sign-ins that cannot start are sent back to the login page --------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("error", "code"),
        [
            (SignInError("unsupported_pkce", "no S256"), "sign_in_failed"),
            (
                PermissionDeniedError("identity:SignIn", "abi:-:-:identity:provider/x"),
                "sign_in_failed",
            ),
            (RuntimeError("boom"), "sign_in_failed"),
        ],
    )
    async def test_a_sign_in_that_cannot_start_returns_to_the_login_page(
        self, nexus, harness, monkeypatch, error, code
    ):
        client, _, _ = nexus

        async def refused(*args, **kwargs):
            raise error

        monkeypatch.setattr(EngineIdentityGateway, "authorization_url", refused)
        started = await client.get(
            "/api/auth/oidc/login", params={"provider": harness.provider_name}
        )
        assert started.status_code == 302
        assert started.headers["location"] == f"{WEB}/auth/login?sso_error={code}"

    @pytest.mark.asyncio
    async def test_an_unloaded_identity_service_returns_to_the_login_page(
        self, nexus, harness, monkeypatch
    ):
        client, _, _ = nexus
        monkeypatch.setattr(runtime.RUNTIME.identity, "_identity", lambda: None)
        for params in ({}, {"provider": harness.provider_name}, {"email": "a@acme.test"}):
            started = await client.get("/api/auth/oidc/login", params=params)
            assert started.status_code == 302, params
            assert started.headers["location"].startswith(f"{WEB}/auth/login?sso_error="), params

    # -- parallel requests on a session that is due ------------------------------

    @pytest.fixture
    def slow_refresh(self, monkeypatch):
        """The provider answers a refresh late: every parallel request has read
        the session as due before the first refresh completes."""
        refresh = EngineIdentityGateway.refresh

        async def slowly(gateway, *args, **kwargs):
            await asyncio.sleep(0.4)
            return await refresh(gateway, *args, **kwargs)

        monkeypatch.setattr(EngineIdentityGateway, "refresh", slowly)

    @pytest.mark.asyncio
    async def test_parallel_requests_refresh_a_due_session_once(self, nexus, harness, slow_refresh):
        client, _, sessions = nexus
        user = harness.create_user(f"pam-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        async with sessions() as db:
            stored = (await db.execute(select(AuthSessionModel))).scalars().all()
            first_token = stored[0].refresh_token_enc
            await db.execute(update(AuthSessionModel).values(refresh_at=stored[0].created_at))
            await db.commit()

        answers = await asyncio.gather(*(client.get("/api/auth/me") for _ in range(5)))
        assert [a.status_code for a in answers] == [200] * 5, [a.text for a in answers]
        async with sessions() as db:
            session = (await db.execute(select(AuthSessionModel))).scalars().one()
            assert session.revoked_at is None
            # The provider vouched again, and (when it rotates) a new token is kept.
            assert session.refresh_at > session.created_at
            assert session.refresh_token_enc and session.refresh_token_enc != first_token
        assert (await client.get("/api/auth/me")).status_code == 200

    # -- the first sign-in of a user ---------------------------------------------

    @pytest.mark.asyncio
    async def test_a_user_inserted_by_a_concurrent_sign_in_is_reused(self, nexus, harness):
        _, _, sessions = nexus
        now = datetime_now()
        fields = {
            "user_id": "prin_one",
            "email": f"max-{os.urandom(3).hex()}@example.com",
            "name": "Max",
            "principal_id": "prin_one",
            "provider": harness.provider_name,
            "issuer": harness.issuer,
            "subject": "sub-one",
            "now": now,
        }
        async with sessions() as first, sessions() as second:
            created = await OidcSessionSecondaryAdapterPostgres(first).create_user(**fields)
            await first.commit()
            # The second flush loses the race: it reads the winner's row.
            adapter = OidcSessionSecondaryAdapterPostgres(second)
            again = await adapter.create_user(**fields)
            assert again.id == created.id and again.principal_id == "prin_one"
            # The session is usable after the rollback.
            assert await adapter.user_by_principal("prin_one") is not None
            # Another account holding the email is a conflict, not a 500.
            with pytest.raises(UserConflictError):
                await adapter.create_user(
                    **{
                        **fields,
                        "user_id": "prin_two",
                        "principal_id": "prin_two",
                        "subject": "sub-two",
                    }
                )


class TestNexusSignInWithFakeIdP(NexusSignInContract):
    @pytest.fixture(scope="class")
    def harness(self):
        with FakeIdP(redirect_uri=CALLBACK) as idp:
            yield idp

    @pytest.mark.asyncio
    async def test_an_unverified_email_is_never_stored_as_such(self, nexus, harness):
        client, _, _ = nexus
        email = f"lou-{os.urandom(3).hex()}@example.com"
        user = harness.create_user(email)
        harness._users[user.subject].email_verified = False
        await self._sign_in(client, harness, user)
        me = (await client.get("/api/auth/me")).json()
        # Nothing looked up by email (an invitation) can find this account.
        assert me["email"] == f"{me['id']}@unverified.internal"

    @pytest.mark.asyncio
    async def test_parallel_requests_spend_a_rotated_refresh_token_once(
        self, nexus, harness, slow_refresh
    ):
        client, _, sessions = nexus
        user = harness.create_user(f"quin-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        async with sessions() as db:
            await db.execute(
                update(AuthSessionModel).values(refresh_at=datetime_now() - timedelta(seconds=1))
            )
            await db.commit()
        before = [r for r in harness.token_requests if r.get("grant_type") == "refresh_token"]
        answers = await asyncio.gather(*(client.get("/api/auth/me") for _ in range(6)))
        assert all(a.status_code == 200 for a in answers)
        grants = [r for r in harness.token_requests if r.get("grant_type") == "refresh_token"]
        assert len(grants) - len(before) == 1

    @pytest.mark.asyncio
    async def test_a_refresh_without_an_id_token_keeps_the_session(self, nexus, harness):
        client, iam, sessions = nexus
        claim = f"ops-{os.urandom(3).hex()}"
        with as_service_account("engine"):
            group = iam.create_group("Ops")
            iam.map_idp_group(harness.provider_name, claim, group.id)
        user = harness.create_user(f"rae-{os.urandom(3).hex()}@example.com", groups=[claim])
        await self._sign_in(client, harness, user)
        async with sessions() as db:
            before = (await db.execute(select(AuthSessionModel))).scalars().one()
            kept = (before.group_ids, before.id_token_enc)
            await db.execute(update(AuthSessionModel).values(refresh_at=before.created_at))
            await db.commit()
        harness.refresh_returns_id_token = False
        try:
            assert (await client.get("/api/auth/me")).status_code == 200
        finally:
            harness.refresh_returns_id_token = True
        async with sessions() as db:
            after = (await db.execute(select(AuthSessionModel))).scalars().one()
            assert after.revoked_at is None and after.refresh_at > after.created_at
            # Neither the groups nor the ID token (the logout hint) were dropped.
            assert (after.group_ids, after.id_token_enc) == kept
        assert (await client.get("/api/whoami")).json()["groups"] == [group.id]

    @pytest.mark.asyncio
    async def test_a_refresh_the_provider_refuses_ends_the_session(self, nexus, harness):
        client, _, sessions = nexus
        user = harness.create_user(f"sol-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        harness._refresh.clear()  # the provider forgot every refresh token
        async with sessions() as db:
            await db.execute(
                update(AuthSessionModel).values(refresh_at=datetime_now() - timedelta(seconds=1))
            )
            await db.commit()
        assert (await client.get("/api/auth/me")).status_code == 401
        async with sessions() as db:
            assert (await db.execute(select(AuthSessionModel))).scalars().one().revoked_at


class TestNexusSignInWithZitadel(NexusSignInContract):
    @pytest.fixture(scope="class")
    def harness(self):
        from naas_abi_core.services.identity.tests.zitadel_server import (
            BinariesUnavailable,
            ZitadelHarness,
            ZitadelServer,
        )

        try:
            server = ZitadelServer().start()
        except BinariesUnavailable as exc:
            if os.environ.get("ABI_REQUIRE_ZITADEL") == "1":
                raise
            pytest.skip(f"Zitadel is not available: {exc}")
        try:
            yield ZitadelHarness(server, redirect_uri=CALLBACK)
        finally:
            server.stop()
