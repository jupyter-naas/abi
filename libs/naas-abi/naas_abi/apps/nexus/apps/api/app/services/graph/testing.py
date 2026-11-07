"""Test helpers for the knowledge routers (graph, views, ontology, maps).

A real IAM with every feature on for every role (so a role's rights, not a
section's flag, decide), two workspaces with a user of each role
(``viewer``, ``member``, ``admin``, ``owner`` in ``ws-1``; ``viewer2``,
``member2``, ``admin2``, ``owner2`` in ``ws-2``), ``stranger`` who holds
nothing and ``root`` the platform administrator. Requests act as the user their
``X-User`` header names, as the real middleware does for a verified session.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_released,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import use_call_context
from starlette.types import ASGIApp, Receive, Scope, Send

ROLES = ("viewer", "member", "admin", "owner")


@contextmanager
def knowledge_team() -> Iterator[NexusIam]:
    everything = list(KNOWN_FEATURE_KEYS)
    flags = FeatureFlagsConfig(
        enabled_features=everything, role_baseline=dict.fromkeys(ROLES, everything)
    )
    nexus = NexusIam(flags)
    org = nexus.org("org-1")
    for suffix, workspace in (("", "ws-1"), ("2", "ws-2")):
        scope = nexus.workspace("org-1", workspace)
        for role in ROLES:
            nexus.grant(f"{role}{suffix}", role, scope)
            # Members of the org, not its administrators: an org owner or admin
            # reaches every workspace of the org, and these are workspace roles.
            nexus.grant(f"{role}{suffix}", "member", org)
    nexus.user("stranger")
    nexus.platform_admin("root")
    with nexus.installed():
        yield nexus


class AsUser:
    """Run each request as the user ``X-User`` names: ``api`` on behalf of them."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = dict(scope.get("headers") or [])
        user = headers.get(b"x-user", b"").decode() or None
        with use_call_context(NexusIam.context(user)):
            await self.app(scope, receive, send)


def acting_as_header(app: FastAPI) -> FastAPI:
    """Sign requests in as the ``X-User`` header's user and run them as that user."""

    def current_user(request: Request) -> SimpleNamespace:
        return SimpleNamespace(id=request.headers["x-user"], is_superadmin=False)

    app.dependency_overrides[get_current_user_required] = current_user
    app.dependency_overrides[get_current_user_released] = current_user
    app.add_middleware(AsUser)
    return app


def client(app: FastAPI, user: str) -> AsyncClient:
    """A client acting as ``user``. A handler that fails after authorizing is a
    500 answer, not a test error: these tests are about who is let in."""
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"x-user": user},
    )
