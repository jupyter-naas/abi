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


CONTAINER = "abi:nexus:organization/acme/nexus:workspace/viewed"
# The reads of the workspace's Roles & permissions pages: they name the container they manage
# by ``scope`` (IAM's own name of a place), not by ``workspace_id``.
IAM_SCOPED_READS = {
    "/api/iam/admin/access",
    "/api/iam/admin/grantable",
    "/api/iam/admin/publishers",
    "/api/iam/admin/resources",
    "/api/iam/admin/catalogs",
    "/api/iam/admin/policies",
    "/api/iam/admin/attachments",
    "/api/iam/admin/attachable-policies",
    "/api/iam/admin/groups",
}


def _scoped(app, scope: str | bytes, path: str = "/api/iam/admin/access") -> Verdict:
    from urllib.parse import quote

    query = scope if isinstance(scope, bytes) else f"scope={quote(scope, safe='')}".encode()
    return classify("GET", _route(app, "GET", path), {}, query, "viewed", CONTAINER)


def test_the_roles_and_permissions_reads_of_the_workspace_name_it_by_their_scope(app) -> None:
    """Roles & permissions at a workspace reads IAM's admin routes with ``scope=<its container>``
    (or something below it): those are the workspace's own pages, answered as the person."""
    from fastapi.dependencies.utils import get_flat_dependant

    declared = {
        path
        for (method, path), route in _routes(app).items()
        if method == "GET"
        and path.startswith("/api/iam/admin/")
        and any(p.alias == "scope" for p in get_flat_dependant(route.dependant).query_params)
    }
    assert declared == IAM_SCOPED_READS  # a new scoped read is decided here, not by accident
    for path in sorted(IAM_SCOPED_READS):
        for scope in (CONTAINER, CONTAINER + "/*", CONTAINER + "/dev_people:project/p1"):
            assert _scoped(app, scope, path) is Verdict.NAMED, (path, scope)


def test_a_scope_outside_the_viewed_container_names_nothing(app) -> None:
    for scope in (
        "abi:",  # the platform
        "abi:nexus:organization/acme",  # the organisation above
        "abi:nexus:organization/acme/*",
        "abi:nexus:organization/acme/nexus:workspace/other",  # a sibling
        CONTAINER + "x",  # a name that merely starts like it
        CONTAINER.upper(),
        "",
    ):
        assert _scoped(app, scope) is Verdict.OUTSIDE, scope
    assert _scoped(app, b"") is Verdict.OUTSIDE  # no scope: the platform's
    from urllib.parse import quote

    both = f"scope={quote(CONTAINER, safe='')}&scope=abi%3A".encode()
    assert _scoped(app, both) is Verdict.OUTSIDE  # every scope named must be inside
    assert (
        classify("GET", _route(app, "GET", "/api/iam/admin/access"), {}, b"", "viewed", None)
        is Verdict.OUTSIDE
    )


def test_the_scope_of_another_route_is_no_iam_scope(app) -> None:
    """The files' ``scope`` is ``workspace`` or ``my_drive``: only IAM's admin reads are held
    by an IAM scope, and a route that names none of the viewed workspace stays outside."""
    from urllib.parse import quote

    route = _route(app, "GET", "/api/files/")
    query = f"scope={quote(CONTAINER, safe='')}".encode()
    assert classify("GET", route, {}, query, "viewed", CONTAINER) is Verdict.OUTSIDE
    # Reads of the platform's people, groups' members and policies by id name no container.
    for path in (
        "/api/iam/admin/principals",
        "/api/iam/admin/audit",
        "/api/iam/admin/service-accounts",
        "/api/iam/admin/principals/{principal_id}",
    ):
        route = _route(app, "GET", path)
        assert classify("GET", route, {}, query, "viewed", CONTAINER) is Verdict.OUTSIDE, path


def test_a_group_is_read_by_id_in_a_view_and_held_to_the_container_by_its_handler(app) -> None:
    """The Roles & permissions page reads each group of the workspace by id: no workspace in the
    request, so the route is answered, and its handler holds the group's owner to the container."""
    key = ("GET", "/api/iam/admin/groups/{group_id}")
    assert key in ANSWERED_WITHOUT_A_WORKSPACE
    assert "container" in ANSWERED_WITHOUT_A_WORKSPACE[key]


def test_outside_this_view_holds_what_is_owned_inside_the_container() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.view_as.active import use_view
    from naas_abi.apps.nexus.apps.api.app.services.view_as.testing import a_view

    here = "abi:nexus:organization/acme/nexus:workspace/alpha"
    assert confinement.outside_this_view("abi:nexus:organization/acme") is None  # no view
    with use_view(a_view(container=here)):
        assert confinement.outside_this_view(here) is None
        assert confinement.outside_this_view(f"{here}/dev_people:project/p1") is None
        for owner in (None, "abi:", f"{here}x", "abi:nexus:organization/acme"):
            assert confinement.outside_this_view(owner) == (
                "Outside this view: you are viewing as Carol in Alpha"
            ), owner


# What the shell and the workspace's pages ask that names no workspace: each is answered as the
# person, and its handler holds it to the viewed workspace (or it is the platform's, the same
# for every workspace). The pages' other calls of that kind are not asked in a view (the web).
SHELL_READS = (
    ("GET", "/api/organizations/{org_id}", "organization"),
    ("GET", "/api/providers/models", "catalog"),
    ("GET", "/api/iam/admin/policies/{policy_id}", "owner"),
    ("GET", "/api/iam/admin/principals/{principal_id}/groups", "owner"),
)


def test_the_reads_the_shell_and_the_pages_make_are_answered_with_their_reason(app) -> None:
    routes = _routes(app)
    for method, path, why in SHELL_READS:
        key = (method, path)
        assert key in ANSWERED_WITHOUT_A_WORKSPACE, key
        assert why in ANSWERED_WITHOUT_A_WORKSPACE[key], key
        assert _verdict(method, routes[key]) is Verdict.LISTED, key


def test_the_reads_that_would_list_the_organization_or_another_person_stay_outside(app) -> None:
    """The members and the workspaces of the organization (the pickers of Settings › General),
    a person read by id and the platform's people are not part of a view: the web does not ask."""
    for path in (
        "/api/organizations/{org_id}/members",
        "/api/organizations/{org_id}/workspaces",
        "/api/organizations",
        "/api/iam/admin/principals",
        "/api/iam/admin/principals/{principal_id}",
    ):
        route = _route(app, "GET", path)
        assert _verdict("GET", route) is Verdict.OUTSIDE, path
        assert ("GET", path) not in ANSWERED_WITHOUT_A_WORKSPACE, path


def test_outside_this_view_can_hold_what_is_owned_above_the_container() -> None:
    """A policy or a group of the organization (or the platform's policy) is what the page of
    the workspace lists beside its own; another workspace's, or another organization's, is not."""
    from naas_abi.apps.nexus.apps.api.app.services.view_as.active import use_view
    from naas_abi.apps.nexus.apps.api.app.services.view_as.testing import a_view

    here = "abi:nexus:organization/acme/nexus:workspace/alpha"
    refusal = "Outside this view: you are viewing as Carol in Alpha"
    assert (
        confinement.outside_this_view("abi:nexus:organization/zeta", above=True) is None
    )  # no view
    with use_view(a_view(container=here)):
        for owner in (here, f"{here}/dev_people:project/p1", "abi:nexus:organization/acme"):
            assert confinement.outside_this_view(owner, above=True) is None, owner
        assert confinement.outside_this_view(None, above=True) is None  # the platform's policies
        assert confinement.outside_this_view("abi:", above=True) is None
        for owner in (
            "abi:nexus:organization/acme/nexus:workspace/bravo",
            "abi:nexus:organization/zeta",
            "abi:nexus:organization/zeta/nexus:workspace/alpha",
            f"{here}x",
        ):
            assert confinement.outside_this_view(owner, above=True) == refusal, owner
        # A group by id is not given the platform or the organization (``above`` is off).
        assert confinement.outside_this_view("abi:nexus:organization/acme") == refusal


def test_an_organization_is_held_to_the_viewed_workspaces() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.view_as.active import use_view
    from naas_abi.apps.nexus.apps.api.app.services.view_as.testing import a_view

    here = "abi:nexus:organization/acme/nexus:workspace/alpha"
    assert confinement.outside_this_organization("zeta") is None  # no view
    with use_view(a_view(container=here)):
        assert confinement.outside_this_organization("acme") is None
        for org in ("zeta", "acm", "acme/x", ""):
            assert confinement.outside_this_organization(org) == (
                "Outside this view: you are viewing as Carol in Alpha"
            ), org
    # A workspace in no organization has none to read.
    with use_view(a_view(container="abi:nexus:workspace/solo")):
        assert confinement.outside_this_organization("acme") is not None
