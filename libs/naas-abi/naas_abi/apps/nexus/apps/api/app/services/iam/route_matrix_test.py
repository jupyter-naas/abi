"""Viewers read, members write, admins administer: proven for every route.

Every Nexus route declares the IAM action it authorizes, with ``guard`` (a
dependency that checks before the body is read) or ``declares`` (inline checks).
This test reads those declarations off the real application and decides each
with a real IAM:

* no route is left without a declaration, unless it is public or about the
  caller's own account (the lists below, each with its reason);
* a write method never maps to a read action (the few reads sent by POST are
  listed);
* for every ``guard``, a viewer, member, admin and owner are decided by the
  level of the action, and a stranger by nothing.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from naas_abi import ABIModule, NexusConfig
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.main_public_routes_test import PUBLIC_ROUTES
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AuthzDenied
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import (
    LEVEL_OF,
    TYPE_OF,
    TYPES_BY_NAME,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import Declared, Guard
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_scope
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

# Signed-in routes about the caller's own account or the platform's login: no
# workspace role applies. (method, path) -> why.
ACCOUNT_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/api/auth/me"): "the signed-in user's own profile",
    ("PATCH", "/api/auth/me"): "the signed-in user edits their own profile",
    ("POST", "/api/auth/change-password"): "the signed-in user's own password",
    ("POST", "/api/auth/logout"): "ends the caller's own session",
    ("POST", "/api/auth/upload-avatar"): "the signed-in user's own avatar",
    ("DELETE", "/api/auth/avatar"): "the signed-in user's own avatar",
    ("GET", "/api/admin/me"): "whether the caller is a platform admin; answers false, never 403",
    ("GET", "/api/ollama/status"): "reachability of the local model runtime, for any signed-in user",
    ("POST", "/api/search/"): "an empty stub that reads nothing of any workspace",
    ("POST", "/api/search/web"): "public web engines (Wikipedia, DuckDuckGo): no tenant data",
    ("GET", "/api/search/suggestions"): "Wikipedia suggestions: no tenant data",
    ("GET", "/api/search/topics/contract"): "the static placeholders of the topic query roles",
    ("GET", "/api/invitations/providers"): "the identity providers an invitation can go through: no tenant data",
    ("GET", "/api/platform/cli"): "the abi-platform CLI script, the same text for everyone",
    ("GET", "/api/websocket/websocket/presence/user/{user_id}"): "the caller's own presence; another user's is refused",
}

# Reads that travel as POST (a query body): a viewer may send them.
READS_BY_POST: dict[tuple[str, str], str] = {
    ("POST", "/api/graph/explorer/catalog"): "reads graphs: the body names the workspace and graphs",
    ("POST", "/api/graph/explorer/overview"): "reads graphs: the body names the workspace and graphs",
    ("POST", "/api/graph/explorer/instances"): "reads graphs: the body names the workspace and graphs",
    ("POST", "/api/graph/explorer/network"): "reads graphs: the body names the workspace and graphs",
    ("POST", "/api/graph/analyze"): "counts the triples of an uploaded file in memory; stores nothing",
    ("POST", "/api/graph/discovery/relation-targets"): "reads graphs: the body names the filters",
    ("POST", "/api/graph/discovery/properties"): "reads graphs: the body names the filters",
    ("POST", "/api/graph/discovery/instances"): "reads graphs: the body names the filters",
    ("POST", "/api/graph/discovery/instance-detail"): "reads graphs: the body names the individual",
    ("POST", "/api/graph/discovery/relation-types"): "reads graphs: the body names the filters",
    ("POST", "/api/graph/discovery/relations"): "reads graphs: the body names the filters",
    ("POST", "/api/graph/discovery/triples-export"): "serializes the triples the body carries; reads nothing",
    ("POST", "/api/graph/network/node-properties"): "reads graphs: the body names the node",
    ("POST", "/api/graph/network/node-instances"): "reads graphs: the body names the node",
    ("POST", "/api/graph/query"): "read-only query over graphs: the body carries the spec",
    ("POST", "/api/graph/query/facets"): "read-only query over graphs: the body carries the spec",
    ("POST", "/api/view/filters/preview"): "previews triples of graphs: the body carries the filters",
    ("POST", "/api/datasets/{namespace}/query"): "read-only SQL: the body carries the query",
    ("POST", "/api/search/private"): "a search of the workspace's sources: the body carries the query",
    ("POST", "/api/apps/access-token"): "mints a link to an app the caller may use",
    ("POST", "/api/apps/remote-grant"): "mints a link to an app the caller may use",
    ("POST", "/api/apps/sso-token"): "mints a sign-in token for a portal the caller may use",
    ("POST", "/api/app-projects/{slug}/preview-token"): "mints a link to view a draft",
    ("POST", "/api/chat/conversations/{conversation_id}/export"): "downloads a conversation the caller owns",
    ("POST", "/api/v1/chat/completions"): "runs an agent for the caller (UseAgent); the gateway stores nothing",
    ("POST", "/api/speech"): "synthesizes speech for the caller; stores nothing",
    ("POST", "/api/speech/"): "synthesizes speech for the caller; stores nothing",
    ("POST", "/api/transcribe"): "transcribes audio for the caller; stores nothing",
    ("POST", "/api/transcribe/"): "transcribes audio for the caller; stores nothing",
}

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ROLES = ("viewer", "member", "admin", "owner")
LEVELS = {
    "list": (True, True, True, True),
    "read": (True, True, True, True),
    "write": (False, True, True, True),
    "admin": (False, False, True, True),
}
# Platform-level types are reached by the platform admin alone, bar the model
# list the built-in roles carry (roles.PLATFORM_TYPES).
PLATFORM_VIEWER_ACTIONS = {"ListProviderModels", "GetProviderModel"}


def level_of(action: str) -> str:
    """The level of a ``nexus`` action, or of a kernel action (``service:Action``)
    a route performs for the user through the kernel's own check."""
    if ":" not in action:
        return LEVEL_OF[action]
    service, name = action.split(":")
    from naas_abi_core.services.iam.iam_catalog import CATALOG as IAM_CATALOG
    from naas_abi_core.services.iam.kernel_catalogs import kernel_catalogs

    catalog = next(c for c in (IAM_CATALOG, *kernel_catalogs()) if c.service == service)
    spec = catalog.action(name)
    assert spec is not None, action
    return spec.level


def _calls(dependant):
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _calls(dependency)


@pytest.fixture(scope="module")
def table() -> dict[tuple[str, str], list]:
    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

        app = FastAPI()
        main._register_routes(app)
    found: dict[tuple[str, str], list] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                found[(method, route.path)] = list(_calls(route.dependant))
    return found


def _declared(calls) -> list[Guard | Declared]:
    return [call for call in calls if isinstance(call, Guard | Declared)]


def _superadmin_guarded(calls) -> bool:
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
        require_superadmin,
    )

    return require_superadmin in calls


def _open(table) -> list[tuple[str, str]]:
    return sorted(
        key
        for key, calls in table.items()
        if key not in PUBLIC_ROUTES
        and key not in ACCOUNT_ROUTES
        and not _declared(calls)
        and not _superadmin_guarded(calls)
    )


def test_every_route_declares_the_action_it_authorizes(table) -> None:
    assert _open(table) == []


def test_the_allowlists_have_no_stale_entries(table) -> None:
    assert sorted(set(ACCOUNT_ROUTES) - set(table)) == []
    assert sorted(set(READS_BY_POST) - set(table)) == []
    assert sorted(set(ACCOUNT_ROUTES) & set(PUBLIC_ROUTES)) == []


def test_a_write_method_never_authorizes_only_a_read(table) -> None:
    offenders = []
    for key, calls in table.items():
        if key[0] not in WRITE_METHODS or key in READS_BY_POST:
            continue
        declared = _declared(calls)
        if declared and all(level_of(d.action) in ("list", "read") for d in declared):
            offenders.append(key)
    assert sorted(offenders) == []


def _request(guard: Guard) -> SimpleNamespace:
    params = {}
    if guard.workspace:
        params[guard.workspace] = "ws-1"
    if guard.org:
        params[guard.org] = "org-1"
    for name in guard.id:
        params.setdefault(name, "x")
    return SimpleNamespace(path_params=params, query_params={})


@pytest.fixture(scope="module")
def world():
    everything = list(KNOWN_FEATURE_KEYS)
    flags = FeatureFlagsConfig(
        enabled_features=everything,
        role_baseline=dict.fromkeys((*ROLES, "viewer"), everything),
    )
    nexus = NexusIam(flags)
    workspace = nexus.workspace("org-1", "ws-1")
    organization = org_scope("org-1")
    for role in ROLES:
        nexus.grant(role, role, workspace)
        nexus.grant(role, role, organization)
    nexus.user("stranger")
    nexus.platform_admin("root")
    with nexus.installed():
        yield nexus


def _guards(table) -> list[tuple[tuple[str, str], Guard]]:
    return sorted(
        (
            (key, call)
            for key, calls in table.items()
            for call in calls
            if isinstance(call, Guard)
        ),
        key=lambda pair: (pair[0], pair[1].action),
    )


# Admin-level actions only an owner holds (roles.py ``_OWNER_ONLY_ACTIONS``).
OWNER_ONLY_ACTIONS = {"DeleteWorkspace", "DeleteOrganization"}


def _expected(guard: Guard) -> tuple[bool, ...]:
    if guard.action in OWNER_ONLY_ACTIONS:
        return (False, False, False, True)
    kind = TYPES_BY_NAME[TYPE_OF[guard.action]]
    if kind.placement == "platform":
        viewer_reads = guard.action in PLATFORM_VIEWER_ACTIONS
        return (viewer_reads, viewer_reads, viewer_reads, viewer_reads)
    return LEVELS[LEVEL_OF[guard.action]]


@pytest.mark.asyncio
async def test_guards_decide_by_level_for_every_role(table, world) -> None:
    guards = _guards(table)
    assert len(guards) >= 0
    wrong = []
    for key, guard in guards:
        kind = TYPES_BY_NAME[TYPE_OF[guard.action]]
        if kind.personal:
            continue  # decided on the caller's own resources: proven inline
        request = _request(guard)
        seen = []
        for user in (*ROLES, "stranger", "root"):
            try:
                await guard(request, SimpleNamespace(id=user))
                seen.append(True)
            except AuthzDenied:
                seen.append(False)
        want = _expected(guard)
        if (tuple(seen[:4]), seen[4], seen[5]) != (want, False, True):
            wrong.append((key, guard.action, seen))
    assert wrong == []
