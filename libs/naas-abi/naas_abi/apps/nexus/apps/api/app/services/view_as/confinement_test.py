"""Every route of the application is classified for a view, like the route matrix: it
names the viewed workspace, it is on the list of routes answered without one (each
with its reason), or it is outside the view. Writes are refused before any of that."""

from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from naas_abi import ABIModule, NexusConfig
from naas_abi.apps.nexus.apps.api.app.services.view_as import confinement
from naas_abi.apps.nexus.apps.api.app.services.view_as.confinement import (
    ANSWERED_WITHOUT_A_WORKSPACE,
    ENDING_ROUTES,
    READ_METHODS,
    Verdict,
    classify,
)


@pytest.fixture(scope="module")
def app() -> FastAPI:
    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

        app = FastAPI()
        main._register_routes(app)
    return app


def _routes(app: FastAPI) -> dict[tuple[str, str], APIRoute]:
    return {
        (method, route.path): route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def _verdict(method: str, route: APIRoute) -> Verdict:
    """How a view treats a request of ``method`` that names the viewed workspace wherever
    the route can take one: what the route allows at best."""
    params = {"workspace_id": "viewed"}
    return classify(method, route, params, b"workspace_id=viewed", "viewed")


def test_every_read_route_is_classified(app) -> None:
    classes: dict[Verdict, list[tuple[str, str]]] = {v: [] for v in Verdict}
    for (method, path), route in _routes(app).items():
        if method in READ_METHODS:
            classes[_verdict(method, route)].append((method, path))
    assert sum(len(found) for found in classes.values()) == len(
        [key for key in _routes(app) if key[0] in READ_METHODS]
    )
    assert classes[Verdict.NAMED] and classes[Verdict.LISTED] and classes[Verdict.OUTSIDE]


def test_the_list_of_routes_answered_without_a_workspace_is_exact(app) -> None:
    routes = _routes(app)
    assert sorted(set(ANSWERED_WITHOUT_A_WORKSPACE) - set(routes)) == []  # no stale entry
    for (method, path), reason in ANSWERED_WITHOUT_A_WORKSPACE.items():
        assert method == "GET", (method, path)  # a write is never answered
        assert len(reason) > 20, (method, path)  # each says why it is there
        assert _verdict(method, routes[(method, path)]) is Verdict.LISTED


def test_the_routes_that_end_a_view_exist(app) -> None:
    assert sorted(ENDING_ROUTES - set(_routes(app))) == []


def test_a_workspace_is_named_workspace_id_everywhere(app) -> None:
    """A route that names a workspace by another parameter would be outside every
    view: the day one is added, this says so."""
    odd = []
    for (method, path), route in _routes(app).items():
        for name in route.param_convertors:
            if name != "workspace_id" and re.search(r"workspace|(^|_)ws(_|$)", name):
                odd.append((method, path, name))
    assert odd == []


def test_organization_pages_and_the_platform_are_outside_the_view(app) -> None:
    outside = []
    for (method, path), route in _routes(app).items():
        if method not in READ_METHODS or (method, path) in ANSWERED_WITHOUT_A_WORKSPACE:
            continue
        platform = path.startswith(("/api/admin/", "/api/iam/", "/api/platform/"))
        organization = path.startswith("/api/organizations/") and not route_names_workspace(route)
        if (platform or organization) and _verdict(method, route) is not Verdict.OUTSIDE:
            outside.append((method, path))
    assert outside == []


def route_names_workspace(route: APIRoute) -> bool:
    return confinement.route_names_workspace(route)


def test_the_workspace_pages_name_it(app) -> None:
    routes = _routes(app)
    for key in (
        ("GET", "/api/workspaces/{workspace_id}"),
        ("GET", "/api/workspaces/{workspace_id}/members"),
        ("GET", "/api/graph/list"),
        ("GET", "/api/files/"),
        ("GET", "/api/secrets/{workspace_id}"),
    ):
        assert _verdict(*key[:1], routes[key]) is Verdict.NAMED, key


def _route(app, method, path):
    return _routes(app)[(method, path)]


def test_a_workspace_in_the_query_of_a_route_that_takes_none_names_nothing(app) -> None:
    route = _route(app, "GET", "/api/organizations/{org_id}/members")
    assert classify("GET", route, {"org_id": "acme"}, b"workspace_id=viewed", "viewed") is (
        Verdict.OUTSIDE
    )


def test_every_workspace_named_must_be_the_viewed_one(app) -> None:
    route = _route(app, "GET", "/api/graph/list")
    for query, want in (
        (b"workspace_id=viewed", Verdict.NAMED),
        (b"workspace_id=viewed&workspace_id=other", Verdict.OUTSIDE),
        (b"workspace_id=other", Verdict.OUTSIDE),
        (b"workspace_id=", Verdict.OUTSIDE),
        # A blank value reaches the handler as "" (the last one): it is given, and not the viewed one.
        (b"workspace_id=viewed&workspace_id=", Verdict.OUTSIDE),
        (b"workspace_id=&workspace_id=viewed", Verdict.OUTSIDE),
        (b"", Verdict.OUTSIDE),
    ):
        assert classify("GET", route, {}, query, "viewed") is want, query
    path_route = _route(app, "GET", "/api/workspaces/{workspace_id}/members")
    assert classify("GET", path_route, {"workspace_id": "other"}, b"", "viewed") is Verdict.OUTSIDE


def test_every_write_is_read_only_whatever_it_names(app) -> None:
    scope = {
        "type": "http",
        "path": "/api/workspaces/viewed/members",
        "method": "POST",
        "query_string": b"",
        "app": app,
    }
    refusal = confinement.judge(
        scope, person="Carol", workspace_id="viewed", workspace_name="Alpha"
    )
    assert refusal is not None and refusal.detail == "Read-only: you are viewing as Carol"
    stop = {**scope, "path": "/api/iam/view-as", "method": "DELETE"}
    assert (
        confinement.judge(stop, person="Carol", workspace_id="viewed", workspace_name="A") is None
    )
    out = {**scope, "path": "/api/auth/oidc/logout", "method": "POST"}
    assert confinement.judge(out, person="Carol", workspace_id="viewed", workspace_name="A") is None
    # The cache's own route is no route of the application: refused as any write.
    cache = {**scope, "path": "/api/settings-cache/refresh"}
    assert confinement.judge(cache, person="C", workspace_id="viewed", workspace_name="A")
