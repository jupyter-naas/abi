"""Signing in to Nexus through an identity provider, end to end.

Nexus's migrations on SQLite, its request middleware, ``/api/auth`` and
``/api/auth/oidc``, the engine's identity service and IAM, and a provider over
real HTTP: the in-process ``FakeIdP`` always, Zitadel from its pinned native
binary when it is available (``ABI_REQUIRE_ZITADEL=1`` requires it).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, Response
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    OrganizationDomainModel,
    OrganizationModel,
    UserModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (  # noqa: E501
    router as auth_router,
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
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.identity.IdentityPorts import SignInError
from naas_abi_core.services.identity.tests.fake_idp import FakeIdP
from naas_abi_core.services.identity.tests.identity_contract import (
    bootstrapped_iam,
    identity_service,
    provider_of,
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

    @app.get("/api/uploads/x.svg")
    async def uploaded_svg(user=Depends(get_current_user_required)) -> Response:
        """Stands for a member's upload, served to whoever may read it."""
        return Response("<svg xmlns='http://www.w3.org/2000/svg'/>", media_type="image/svg+xml")

    app.add_middleware(RequestIdentityMiddleware)
    return app


class NexusHarness:
    """The fixtures of a sign-in against ``harness``, whose redirect URI is ``CALLBACK``."""

    # The ``provisioning`` setting the provider is configured with.
    provisioning = "none"

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
        provider = replace(provider_of(harness), provisioning=self.provisioning)
        identity = identity_service(harness, iam, providers=[provider])
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



class NexusSignInContract(NexusHarness):
    """Every provider's sign-in: subclasses give the ``harness`` fixture."""

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

        # Every kernel call runs as api on behalf of the principal.
        assert (await client.get("/api/whoami")).json()["user"] == record.id
        assert (await client.get("/api/whoami")).json()["actor"] == "api"
        # Signing in grants nothing: a user holds the roles of its memberships only.
        attached = [a.policy_id for a in iam.store.list_attachments(principal_id=record.id)]
        assert attached == []

    @pytest.mark.asyncio
    async def test_sign_ins_and_outs_are_audited(self, nexus, harness):
        from sqlalchemy import text

        client, _, sessions = nexus
        user = harness.create_user(f"aud-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        csrf = (await client.get("/api/auth/oidc/session")).json()["csrf_token"]
        await client.post("/api/auth/oidc/logout", headers={"X-CSRF-Token": csrf})
        started = await client.get(
            "/api/auth/oidc/login", params={"provider": harness.provider_name}
        )
        client.cookies.clear()
        await client.get(harness.sign_in(started.headers["location"], user))  # another browser

        async with sessions() as db:
            rows = (
                await db.execute(text("SELECT action, success, details FROM audit_logs ORDER BY id"))
            ).all()
        actions = sorted((r.action, bool(r.success)) for r in rows)
        assert actions == [("login", False), ("login", True), ("logout", True)]
        assert any("browser_mismatch" in (r.details or "") for r in rows)

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

    # -- the cookie never authenticates a page or a frame ----------------------------

    NAVIGATIONS = (
        {
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
        },
        {"Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "same-site"},
        {"Sec-Fetch-Dest": "iframe", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Dest": "embed", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Dest": "object", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Site": "same-origin"},
    )

    @pytest.mark.asyncio
    async def test_a_link_to_the_api_is_not_signed_in(self, nexus, harness):
        client, _, _ = nexus
        user = harness.create_user(f"nav-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        for navigation in self.NAVIGATIONS:
            # The uploaded page a member sends an admin must not even be served.
            served = await client.get("/api/uploads/x.svg", headers=navigation)
            assert served.status_code == 401, navigation
            assert "svg" not in served.text
            assert (await client.get("/api/auth/me", headers=navigation)).status_code == 401
            # And it hands out no CSRF token, which is what turns a script into the user.
            session = await client.get("/api/auth/oidc/session", headers=navigation)
            assert session.status_code == 401, navigation
            assert "csrf_token" not in session.text
            assert (await client.get("/api/whoami", headers=navigation)).json()["user"] is None

    @pytest.mark.asyncio
    async def test_the_web_apps_own_requests_still_carry_the_session(self, nexus, harness):
        client, _, _ = nexus
        user = harness.create_user(f"web-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        fetches = (
            {},  # no Fetch Metadata: older browsers, scripts
            {"Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site"},
            {"Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"},
            {"Sec-Fetch-Dest": "image", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Site": "same-site"},
        )
        for headers in fetches:
            assert (await client.get("/api/auth/me", headers=headers)).status_code == 200, headers
            session = await client.get("/api/auth/oidc/session", headers=headers)
            assert session.status_code == 200, headers
            assert session.json()["csrf_token"]
        # A change the web app sends keeps working with its CSRF token.
        csrf = (await client.get("/api/auth/oidc/session")).json()["csrf_token"]
        renamed = await client.patch(
            "/api/auth/me",
            json={"name": "Web"},
            headers={"X-CSRF-Token": csrf, "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors"},
        )
        assert renamed.status_code == 200

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
            db.add(UserModel(id="legacy-ivy", email=email, name="Ivy"))
            await db.commit()
        landed = await self._sign_in(client, harness, harness.create_user(email))
        assert landed.headers["location"] == f"{WEB}/auth/login?sso_error=email_in_use"

    @pytest.mark.asyncio
    async def test_an_email_domain_routes_to_its_provider(self, nexus, harness):
        client, _, sessions = nexus
        async with sessions() as db:
            db.add(
                UserModel(id="owner-1", email="owner@example.com", name="O")
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

    # -- an email no domain maps goes to the default provider ----------------------

    @pytest.fixture
    def with_default(self, nexus, harness):
        """The provider is also the engine's ``default_provider``."""
        identity = runtime.RUNTIME.identity._identity()
        previous, identity._default = identity._default, harness.provider_name
        yield
        identity._default = previous

    @pytest.mark.asyncio
    async def test_an_email_without_a_domain_mapping_goes_to_the_default_provider(
        self, nexus, harness, with_default
    ):
        client, _, _ = nexus
        providers = (await client.get("/api/auth/oidc/providers")).json()
        assert providers["default_provider"] == harness.provider_name
        # Nexus has no login of its own: whoever the domains do not map signs in
        # at the default provider.
        for email in ("admin@example.com", "someone@elsewhere.test"):
            routed = await client.post("/api/auth/oidc/route", json={"email": email})
            assert routed.json() == {"provider": harness.provider_name}
        started = await client.get("/api/auth/oidc/login", params={"email": "admin@example.com"})
        assert urlsplit(started.headers["location"]).netloc == urlsplit(harness.issuer).netloc
        bare = await client.get("/api/auth/oidc/login")
        assert urlsplit(bare.headers["location"]).netloc == urlsplit(harness.issuer).netloc

    @pytest.mark.asyncio
    async def test_a_verified_domain_wins_over_the_default_provider(
        self, nexus, harness, with_default
    ):
        client, _, sessions = nexus
        async with sessions() as db:
            db.add(UserModel(id="owner-2", email="owner2@example.com", name="O"))
            db.add(OrganizationModel(id="org-2", name="Acme", slug="acme2", owner_id="owner-2"))
            db.add(
                OrganizationDomainModel(
                    id="d-3",
                    organization_id="org-2",
                    domain="corp.example",
                    is_verified=True,
                    provider="elsewhere",
                )
            )
            await db.commit()
        routed = await client.post("/api/auth/oidc/route", json={"email": "a@corp.example"})
        assert routed.json() == {"provider": "elsewhere"}

    @pytest.mark.asyncio
    async def test_without_a_default_an_unmapped_email_has_no_provider(self, nexus, harness):
        client, _, _ = nexus
        routed = await client.post("/api/auth/oidc/route", json={"email": "admin@example.com"})
        assert routed.json() == {"provider": None}
        started = await client.get("/api/auth/oidc/login", params={"email": "admin@example.com"})
        assert started.headers["location"] == f"{WEB}/auth/login?sso_error=no_provider"

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


LEGACY_ISSUER = "urn:abi:nexus"


class NexusFirstSignInContract(NexusHarness):
    """A user of the old built-in login signs in for the first time through the
    built-in provider: matched by the verified email, linked to the principal
    that holds its roles, nothing else (RFC §13)."""

    provisioning = "builtin"

    async def _legacy_user(self, sessions, iam, email, *, user_id="user-legacy-1"):
        async with sessions() as db:
            db.add(UserModel(id=user_id, email=email, name="Legacy"))
            await db.commit()
        with as_service_account("engine"):
            principal = iam.ensure_user(LEGACY_ISSUER, user_id, provider="nexus")
            iam.attach_policy("builtin.member", principal.id, "abi:acme:ws1")
        return principal

    @pytest.mark.asyncio
    async def test_the_first_sign_in_links_the_account_and_keeps_its_roles(
        self, nexus, harness
    ):
        client, iam, sessions = nexus
        email = f"lea-{os.urandom(3).hex()}@example.com"
        principal = await self._legacy_user(sessions, iam, email)
        user = harness.create_user(email)

        landed = await self._sign_in(client, harness, user)
        assert landed.headers["location"].startswith(f"{WEB}/auth/callback"), landed.headers

        me = (await client.get("/api/auth/me")).json()
        assert me["id"] == "user-legacy-1"  # its data stays where it was
        assert me["email"] == email
        record = iam.store.find_user(harness.issuer, user.subject)
        assert record is not None and record.id == principal.id
        async with sessions() as db:
            row = (await db.execute(select(UserModel).where(UserModel.id == me["id"]))).scalar_one()
            assert (row.principal_id, row.idp_issuer, row.idp_subject) == (
                principal.id,
                harness.issuer,
                user.subject,
            )
            assert len((await db.execute(select(UserModel))).scalars().all()) == 1
        # Every kernel call names the Nexus id, which IAM resolves to the same user.
        assert (await client.get("/api/whoami")).json()["user"] == "user-legacy-1"
        held = {(a.policy_id, a.scope) for a in iam.store.list_attachments(principal_id=principal.id)}
        assert ("builtin.member", "abi:acme:ws1") in held
        assert [
            p.id for p in iam.store.list_principals("user", limit=100).items if p.status == "active"
        ] == [principal.id]

    @pytest.mark.asyncio
    async def test_the_second_sign_in_is_the_same_account(self, nexus, harness):
        client, iam, sessions = nexus
        email = f"mo-{os.urandom(3).hex()}@example.com"
        principal = await self._legacy_user(sessions, iam, email)
        user = harness.create_user(email)
        await self._sign_in(client, harness, user)
        client.cookies.clear()
        await self._sign_in(client, harness, user)
        assert (await client.get("/api/auth/me")).json()["id"] == "user-legacy-1"
        # The session is vouched for by the linked principal.
        session = (await client.get("/api/auth/oidc/session")).json()
        assert session["user"]["id"] == "user-legacy-1"
        async with sessions() as db:
            stored = (await db.execute(select(AuthSessionModel))).scalars().all()
            assert {s.principal_id for s in stored} == {principal.id}
        with as_service_account("engine"):
            iam.suspend_principal(principal.id)
        assert (await client.get("/api/auth/me")).status_code == 401

    @pytest.mark.asyncio
    async def test_the_email_must_match_exactly_the_verified_one(self, nexus, harness):
        client, iam, sessions = nexus
        await self._legacy_user(sessions, iam, "someone@example.com")
        user = harness.create_user(f"nia-{os.urandom(3).hex()}@example.com")
        await self._sign_in(client, harness, user)
        me = (await client.get("/api/auth/me")).json()
        assert me["id"] != "user-legacy-1"  # another person: another account

    @pytest.mark.asyncio
    async def test_a_suspended_account_is_not_opened_by_the_link(self, nexus, harness):
        client, iam, sessions = nexus
        email = f"oz-{os.urandom(3).hex()}@example.com"
        principal = await self._legacy_user(sessions, iam, email)
        with as_service_account("engine"):
            iam.suspend_principal(principal.id)
        landed = await self._sign_in(client, harness, harness.create_user(email))
        assert landed.headers["location"] == f"{WEB}/auth/login?sso_error=suspended"
        assert (await client.get("/api/auth/me")).status_code == 401
        async with sessions() as db:
            row = (await db.execute(select(UserModel))).scalar_one()
            assert row.principal_id is None  # not linked


class TestFirstSignInWithBuiltinIdP(NexusFirstSignInContract):
    @pytest.fixture(scope="class")
    def harness(self):
        pytest.importorskip("naas_abi_idp")
        from naas_abi_core.services.identity.tests.builtin_idp_server import (
            BuiltinIdPHarness,
        )

        with BuiltinIdPHarness(redirect_uri=CALLBACK) as idp:
            yield idp


class TestFirstSignInWithFakeIdPSettingBuiltin(NexusFirstSignInContract):
    """The provider's own email_verified decides: here a setting of ``builtin``
    on a provider whose users may be unverified."""

    @pytest.fixture(scope="class")
    def harness(self):
        with FakeIdP(redirect_uri=CALLBACK) as idp:
            yield idp

    @pytest.mark.asyncio
    async def test_a_linked_account_is_not_linked_again_to_another_identity(
        self, nexus, harness
    ):
        client, iam, sessions = nexus
        email = f"pat-{os.urandom(3).hex()}@example.com"
        await self._legacy_user(sessions, iam, email)
        await self._sign_in(client, harness, harness.create_user(email))
        client.cookies.clear()
        # Another identity of the same provider claiming the same address (a
        # second account of the provider): the email is held by a linked account.
        other = harness.create_user(email)
        landed = await self._sign_in(client, harness, other)
        assert landed.headers["location"] == f"{WEB}/auth/login?sso_error=email_in_use"

    @pytest.mark.asyncio
    async def test_an_unverified_email_never_links(self, nexus, harness):
        client, iam, sessions = nexus
        email = f"quo-{os.urandom(3).hex()}@example.com"
        await self._legacy_user(sessions, iam, email)
        user = harness.create_user(email)
        harness._users[user.subject].email_verified = False
        await self._sign_in(client, harness, user)
        # The unverified address is not used: the sign-in is a new account.
        me = (await client.get("/api/auth/me")).json()
        assert me["id"] != "user-legacy-1"
        async with sessions() as db:
            legacy = (
                await db.execute(select(UserModel).where(UserModel.id == "user-legacy-1"))
            ).scalar_one()
            assert legacy.principal_id is None


class TestSettingsOtherThanBuiltinNeverLink(NexusHarness):
    """Only the built-in provider proves an address by mailing it a code."""

    @pytest.fixture(scope="class")
    def harness(self):
        with FakeIdP(redirect_uri=CALLBACK) as idp:
            yield idp

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provisioning", ["none", "zitadel", "keycloak"])
    async def test_a_verified_email_of_another_provider_is_refused(
        self, nexus, harness, monkeypatch, provisioning
    ):
        client, iam, sessions = nexus
        identity = runtime.RUNTIME.identity._identity()
        configured = identity._providers[harness.provider_name]
        monkeypatch.setattr(
            identity, "_providers", {harness.provider_name: replace(configured, provisioning=provisioning)}
        )
        email = f"rex-{os.urandom(3).hex()}@example.com"
        async with sessions() as db:
            db.add(UserModel(id="user-legacy-2", email=email, name="Legacy"))
            await db.commit()
        landed = await self._sign_in(client, harness, harness.create_user(email))
        assert landed.headers["location"] == f"{WEB}/auth/login?sso_error=email_in_use"


class TestLinkingTheRows:
    """The Nexus rows of the old login: found by email, linked once."""

    @pytest_asyncio.fixture
    async def db(self, tmp_path):
        from naas_abi.apps.nexus.apps.api.app.core.database import Base
        from sqlalchemy.ext.asyncio import AsyncSession

        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rows.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(UserModel(id="u-ada", email="Ada@Example.com", name="Ada"))
            session.add(UserModel(id="u-bob", email="bob@example.com", name="Bob"))
            session.add(
                UserModel(
                    id="usr_1",
                    email="carl@example.com",
                    name="Carl",
                    principal_id="usr_1",
                    idp_issuer="https://idp.example",
                    idp_subject="s-carl",
                )
            )
            await session.commit()
            yield session
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_only_the_rows_no_provider_signs_in_are_legacy(self, db) -> None:
        adapter = OidcSessionSecondaryAdapterPostgres(db)

        assert [u.id for u in await adapter.list_legacy_users()] == ["u-ada", "u-bob"]
        assert (await adapter.legacy_user_by_email("ADA@example.com")).id == "u-ada"  # type: ignore[union-attr]
        assert await adapter.legacy_user_by_email("carl@example.com") is None
        assert await adapter.legacy_user_by_email("nobody@example.com") is None

    @pytest.mark.asyncio
    async def test_a_row_is_linked_once_to_one_identity(self, db) -> None:
        adapter = OidcSessionSecondaryAdapterPostgres(db)
        fields = {
            "principal_id": "usr_ada",
            "provider": "builtin",
            "issuer": "https://idp.example",
            "subject": "s-ada",
            "now": datetime_now(),
        }

        linked = await adapter.link_user("u-ada", **fields)
        again = await adapter.link_user("u-ada", **fields)  # a second sign-in of the same person

        assert (linked.id, linked.principal_id, linked.email) == ("u-ada", "usr_ada", "Ada@Example.com")
        assert again == linked
        assert await adapter.legacy_user_by_email("ada@example.com") is None
        # Another identity cannot take a linked row, nor can one identity take two rows.
        with pytest.raises(UserConflictError):
            await adapter.link_user("u-ada", **{**fields, "subject": "s-other", "principal_id": "usr_x"})
        with pytest.raises(UserConflictError):
            await adapter.link_user("u-bob", **fields)
        with pytest.raises(UserConflictError):
            await adapter.link_user("u-missing", **{**fields, "subject": "s-m", "principal_id": "usr_m"})


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

    @pytest.mark.asyncio
    async def test_an_email_the_schemas_cannot_carry_is_never_stored(self, nexus, harness):
        client, _, _ = nexus
        # ".test" is a reserved name: stored, it would fail every request of the user.
        user = harness.create_user(f"mia-{os.urandom(3).hex()}@corp.test")
        await self._sign_in(client, harness, user)
        me = await client.get("/api/auth/me")
        assert me.status_code == 200, me.text
        assert me.json()["email"] == f"{me.json()['id']}@unverified.internal"
        assert (await client.get("/api/auth/oidc/session")).status_code == 200


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


class TestNexusSignInWithBuiltinIdP(NexusSignInContract):
    """The built-in IdP (``naas-abi-idp``): email-code sign-in end to end."""

    @pytest.fixture(scope="class")
    def harness(self):
        pytest.importorskip("naas_abi_idp")
        from naas_abi_core.services.identity.tests.builtin_idp_server import (
            BuiltinIdPHarness,
        )

        with BuiltinIdPHarness(redirect_uri=CALLBACK) as idp:
            yield idp
