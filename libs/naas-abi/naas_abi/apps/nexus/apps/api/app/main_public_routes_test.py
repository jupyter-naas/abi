"""Every Nexus route needs a signed-in caller unless it is listed here.

A new route that forgets its auth dependency fails this test instead of
shipping open to the internet.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from naas_abi import ABIModule, NexusConfig

# (method, path) -> why it is reachable without a session.
PUBLIC_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/health"): "liveness probe",
    ("GET", "/api/tenant"): "branding for the login page",
    ("GET", "/api/organizations/slug/{slug}/branding"): "org login page branding",
    ("GET", "/api/auth/config"): "tells the login page which methods exist",
    ("POST", "/api/auth/register"): "sign-up (off unless auth_signup_enabled)",
    ("POST", "/api/auth/login"): "sign-in",
    ("POST", "/api/auth/token"): "OAuth2 password sign-in",
    ("POST", "/api/auth/refresh"): "exchanges a refresh token",
    ("POST", "/api/auth/forgot-password"): "password reset request",
    ("POST", "/api/auth/reset-password"): "password reset with a token",
    ("POST", "/api/auth/magic-link/request"): "sign-in code request",
    ("POST", "/api/auth/magic-link/verify"): "sign-in with a link token",
    ("POST", "/api/auth/otp/verify"): "sign-in with a code",
    ("GET", "/api/auth/avatar/{filename}"): "avatar images used in <img> tags",
    ("GET", "/app-preview/{token}"): "capability URL (signed preview token)",
    ("GET", "/app-preview/{token}/{path:path}"): "capability URL (signed preview token)",
    ("GET", "/provider-logos/{provider_id}"): "static provider logos",
}

SUPERADMIN_ONLY = {
    ("POST", "/api/ollama/pull"),
    ("POST", "/api/ollama/ensure-ready"),
}


def _dependency_calls(dependant):
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _dependency_calls(dependency)


@pytest.fixture(scope="module")
def routes() -> dict[tuple[str, str], set]:
    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

        app = FastAPI()
        main._register_routes(app)

    table: dict[tuple[str, str], set] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                table[(method, route.path)] = set(_dependency_calls(route.dependant))
    return table


def _auth_guards() -> set:
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
        get_current_user_required,
    )
    from naas_abi_core.apps.api.abi_api_key_auth import require_abi_api_token

    return {get_current_user_required, require_abi_api_token}


def test_every_route_requires_a_signed_in_caller_unless_listed(routes) -> None:
    guards = _auth_guards()
    open_routes = sorted(
        key for key, calls in routes.items() if not calls & guards and key not in PUBLIC_ROUTES
    )

    assert open_routes == []


def test_the_public_allowlist_has_no_stale_entries(routes) -> None:
    assert sorted(set(PUBLIC_ROUTES) - set(routes)) == []


def test_ollama_control_routes_are_superadmin_only(routes) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
        require_superadmin,
    )

    for key in SUPERADMIN_ONLY:
        assert require_superadmin in routes[key], key
