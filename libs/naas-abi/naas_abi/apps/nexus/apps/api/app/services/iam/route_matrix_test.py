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
    NEXUS_ACTIONS,
    TYPE_OF,
    TYPES_BY_NAME,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import Declared, Guard
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.view_as.reads_by_post import READS_BY_POST

# Signed-in routes about the caller's own account or the platform's login: no
# workspace role applies. (method, path) -> why.
ACCOUNT_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/api/auth/me"): "the signed-in user's own profile",
    ("PATCH", "/api/auth/me"): "the signed-in user edits their own profile",
    ("POST", "/api/auth/upload-avatar"): "the signed-in user's own avatar",
    ("DELETE", "/api/auth/avatar"): "the signed-in user's own avatar",
    ("GET", "/api/admin/me"): "whether the caller is a platform admin; answers false, never 403",
    (
        "GET",
        "/api/ollama/status",
    ): "reachability of the local model runtime, for any signed-in user",
    ("POST", "/api/search/"): "an empty stub that reads nothing of any workspace",
    ("POST", "/api/search/web"): "public web engines (Wikipedia, DuckDuckGo): no tenant data",
    ("GET", "/api/search/suggestions"): "Wikipedia suggestions: no tenant data",
    ("GET", "/api/search/topics/contract"): "the static placeholders of the topic query roles",
    (
        "GET",
        "/api/invitations/providers",
    ): "the identity providers an invitation can go through: no tenant data",
    ("GET", "/api/platform/cli"): "the abi-platform CLI script, the same text for everyone",
    ("POST", "/api/analytics/events"): (
        "the caller's own usage events: identity from the token, a workspace kept only "
        "for one of its members"
    ),
    (
        "DELETE",
        "/api/iam/view-as",
    ): "Stop: ends the caller's own view; it gives up a right and asks none",
    ("GET", "/api/iam/admin/access"): "what the caller may do, decided by IAM for the caller only",
    ("GET", "/api/iam/admin/grantable"): (
        "what the caller may grant, decided by IAM for the caller only"
    ),
    ("GET", "/api/iam/admin/publishers"): (
        "what the caller may grant, by publisher, decided by IAM for the caller only"
    ),
    ("GET", "/api/iam/admin/resources"): (
        "what the caller may list of a type, filtered by IAM as the caller"
    ),
    (
        "GET",
        "/api/websocket/websocket/presence/user/{user_id}",
    ): "the caller's own presence; another user's is refused",
}

# Reads that travel as POST (a query body): a viewer may send them. The list is app code
# (``view_as.reads_by_post``): the read-only guard of a view reads it too.
READS_BY_POST_ROUTES = {entry.key for entry in READS_BY_POST}

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ROLES = ("viewer", "member", "admin", "owner")
LEVELS = {
    "list": (True, True, True, True),
    "read": (True, True, True, True),
    "write": (False, True, True, True),
    "admin": (False, False, True, True),
}
# Platform-level types are reached by the platform admin alone, bar the model
# list the platform companions carry (the catalog's PLATFORM_ACCESS): the model list
# and the datasets of the platform, which every workspace role reads.
PLATFORM_VIEWER_ACTIONS = {
    "ListProviderModels",
    "GetProviderModel",
    "ListDatasets",
    "GetDataset",
    "PreviewDataset",
    "QueryDataset",
}


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
    assert sorted(set(READS_BY_POST_ROUTES) - set(table)) == []
    assert sorted(set(ACCOUNT_ROUTES) & set(PUBLIC_ROUTES)) == []


# Workspace settings > General › Features and Agents/Apps: read as the workspace's
# configuration, saved as the IAM write the caller makes on "<W> access"
# (``services/feature_access``).
FEATURE_ACCESS_ROUTES: dict[tuple[str, str], tuple[str, ...]] = {
    ("GET", "/api/workspaces/{workspace_id}/feature-access"): ("GetWorkspaceConfiguration",),
    ("PUT", "/api/workspaces/{workspace_id}/feature-access"): ("iam:UpdatePolicy",),
    ("GET", "/api/workspaces/{workspace_id}/offer"): ("GetWorkspaceConfiguration",),
    ("PUT", "/api/workspaces/{workspace_id}/offer"): ("iam:UpdatePolicy",),
    ("PUT", "/api/workspaces/{workspace_id}/offer/files"): ("iam:UpdatePolicy",),
    ("PUT", "/api/workspaces/{workspace_id}/offer/ontologies"): ("iam:UpdatePolicy",),
}


def test_the_feature_access_routes_declare_what_they_authorize(table) -> None:
    found = {key: tuple(d.action for d in _declared(table[key])) for key in FEATURE_ACCESS_ROUTES}
    assert found == FEATURE_ACCESS_ROUTES


# Access › Groups: IAM decides each change on the group, at the scope that owns it.
GROUP_ROUTES: dict[tuple[str, str], tuple[str, ...]] = {
    ("POST", "/api/iam/admin/groups"): ("iam:CreateGroup",),
    ("PATCH", "/api/iam/admin/groups/{group_id}"): ("iam:UpdateGroup",),
    ("DELETE", "/api/iam/admin/groups/{group_id}"): ("iam:DeleteGroup",),
}


def test_the_group_routes_declare_what_they_authorize(table) -> None:
    found = {key: tuple(d.action for d in _declared(table[key])) for key in GROUP_ROUTES}
    assert found == GROUP_ROUTES


# Access › Groups' capability groups (``iam/capabilities``): listed for whoever lists the
# groups of the level, made (as ``api``) for whoever may create a group there.
CAPABILITY_ROUTES: dict[tuple[str, str], tuple[str, ...]] = {
    ("GET", "/api/iam/admin/capabilities"): ("iam:ListGroups",),
    ("POST", "/api/iam/admin/capabilities"): ("iam:CreateGroup",),
}


def test_the_capability_routes_declare_what_they_authorize(table) -> None:
    found = {key: tuple(d.action for d in _declared(table[key])) for key in CAPABILITY_ROUTES}
    assert found == CAPABILITY_ROUTES


# Workspace settings > General › Platform Files (``iam/platform_files_routes``): read as
# the workspace's configuration, saved as the write the caller makes of "<W> access" (its
# ``GivenPlatformFiles``).
PLATFORM_FILES_ROUTES: dict[tuple[str, str], tuple[str, ...]] = {
    ("GET", "/api/workspaces/{workspace_id}/platform-files"): ("GetWorkspaceConfiguration",),
    ("PUT", "/api/workspaces/{workspace_id}/platform-files"): ("iam:UpdatePolicy",),
}


def test_the_platform_files_routes_declare_what_they_authorize(table) -> None:
    found = {key: tuple(d.action for d in _declared(table[key])) for key in PLATFORM_FILES_ROUTES}
    assert found == PLATFORM_FILES_ROUTES


def test_a_write_method_never_authorizes_only_a_read(table) -> None:
    offenders = []
    for key, calls in table.items():
        if key[0] not in WRITE_METHODS or key in READS_BY_POST_ROUTES:
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
    organization = org_container("org-1")
    for role in ROLES:
        nexus.grant(role, role, workspace)
        nexus.grant(role, role, organization)
    nexus.user("stranger")
    nexus.platform_admin("root")
    with nexus.installed():
        yield nexus


def _guards(table) -> list[tuple[tuple[str, str], Guard]]:
    return sorted(
        ((key, call) for key, calls in table.items() for call in calls if isinstance(call, Guard)),
        key=lambda pair: (pair[0], pair[1].action),
    )


# Admin-level actions only an owner holds: flagged ``owner_only`` in the catalog.
OWNER_ONLY_ACTIONS = {a.spec.name for a in NEXUS_ACTIONS if a.spec.owner_only}


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


def test_the_scoped_analytics_are_guarded_by_their_scope(table) -> None:
    """Organization analytics are its owners' and admins', a workspace's its admins'
    (decided by level above); a conversation's messages also declare the action no
    role holds."""
    found: dict[tuple[str, str], set[str]] = {}
    for key, calls in table.items():
        if "/analytics" in key[1] and key[1].startswith(("/api/organizations", "/api/workspaces")):
            found[key] = {d.action for d in _declared(calls)}
    org = "/api/organizations/{org_id}/analytics"
    workspace = "/api/workspaces/{workspace_id}/analytics"
    for path in (
        "overview",
        "users",
        "users/{user_id}",
        "sessions",
        "pages",
        "events",
        "chats",
        "chat-analytics",
    ):
        assert found[("GET", f"{org}/{path}")] == {"ReadOrganizationAnalytics"}, path
        assert found[("GET", f"{workspace}/{path}")] == {"ReadWorkspaceAnalytics"}, path
    assert found[("GET", f"{org}/workspaces")] == {"ReadOrganizationAnalytics"}
    assert ("GET", f"{workspace}/workspaces") not in found
    for path in ("chats/{conversation_id}", "chats/{conversation_id}/export"):
        assert found[("GET", f"{org}/{path}")] == {
            "ReadOrganizationAnalytics",
            "ReadAnalyticsConversation",
        }
        assert found[("GET", f"{workspace}/{path}")] == {
            "ReadWorkspaceAnalytics",
            "ReadAnalyticsConversation",
        }
    assert found[("GET", f"{org}/access")] == {"ReadOrganizationAnalytics"}
    assert found[("GET", f"{workspace}/access")] == {"ReadWorkspaceAnalytics"}
    assert TYPES_BY_NAME[TYPE_OF["ReadAnalyticsConversation"]].policy_only


# -- levels as groups (#1585) ------------------------------------------------------------

# Who, in a world whose organization and workspace keep their people in groups:
# a Viewer and a Member (their level, "<W> workspace", "<O> people"), a workspace admin
# (Member, "<W> admins"; a Member of the organization), an org admin ("<O> admins"),
# the platform admin and a stranger.
GROUPED = ("viewer", "member", "wadmin", "oadmin", "root", "stranger")


@pytest.fixture(scope="module")
def grouped_world():
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import widen_offer
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer
    from naas_abi_core.engine.call_context import as_service_account

    everything = list(KNOWN_FEATURE_KEYS)
    nexus = NexusIam(FeatureFlagsConfig(enabled_features=everything), features_with_roles=False)
    with nexus.installed():
        org = nexus.grouped_org("org-1", "Org")
        offer = Offer.of(features=everything)
        with as_service_account("api"):
            widen_offer(nexus.iam, org.access_policy_id, offer)
        workspace = nexus.grouped_workspace("org-1", "ws-1", "WS", offer=offer).container
        organization = org_container("org-1")
        for person in GROUPED:
            nexus.user(person)
        nexus.platform_admin("root")

        async def team() -> None:
            await MEMBERSHIPS.grant("oadmin", "admin", organization)
            for person, role in (("viewer", "viewer"), ("member", "member")):
                await MEMBERSHIPS.grant(person, role, workspace)
                await MEMBERSHIPS.grant(person, role, organization)
            await MEMBERSHIPS.grant("wadmin", "admin", workspace)
            await MEMBERSHIPS.grant("wadmin", "member", organization)

        asyncio.run(team())
        yield nexus


def _grouped_expected(guard: Guard) -> tuple[bool, ...]:
    """viewer, member, wadmin, oadmin, root, stranger, by the action's level, where it
    is decided (the organization's own level or the workspace) and its feature (the
    level's features; the org admin's through "<O> access", every one here)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import FEATURE_OF
    from naas_abi.apps.nexus.apps.api.app.services.iam.levels import (
        MEMBER_FEATURES,
        VIEWER_FEATURES,
    )

    if guard.action in OWNER_ONLY_ACTIONS:
        return (False, False, False, False, True, False)
    kind = TYPES_BY_NAME[TYPE_OF[guard.action]]
    if kind.placement == "platform":
        viewer_reads = guard.action in PLATFORM_VIEWER_ACTIONS
        return (viewer_reads,) * 4 + (True, False)
    level = LEVEL_OF[guard.action]
    reads = level in ("list", "read")
    writes = reads or level == "write"
    at_org = guard.org is not None
    viewer, member = reads, writes
    wadmin = writes if at_org else True
    oadmin = True
    feature = FEATURE_OF.get(guard.action) if guard.feature is None else guard.feature
    if feature is not None and not at_org:
        viewer = viewer and feature in VIEWER_FEATURES
        member = member and feature in MEMBER_FEATURES
    return (viewer, member, wadmin, oadmin, True, False)


@pytest.mark.asyncio
async def test_guards_decide_by_level_for_every_level_in_groups(table, grouped_world) -> None:
    """Viewer, Member, workspace admin, org admin, platform admin and a stranger,
    every one through groups: nothing attached to a person."""
    wrong = []
    for key, guard in _guards(table):
        kind = TYPES_BY_NAME[TYPE_OF[guard.action]]
        if kind.personal:
            continue
        request = _request(guard)
        seen = []
        for user in GROUPED:
            try:
                await guard(request, SimpleNamespace(id=user))
                seen.append(True)
            except AuthzDenied:
                seen.append(False)
        if tuple(seen) != _grouped_expected(guard):
            wrong.append((key, guard.action, seen, _grouped_expected(guard)))
    assert wrong == []


def test_deleting_is_the_org_admins_and_the_platform_admins(table) -> None:
    """Owner is no longer assigned (#1585): a workspace of an organization is deleted
    by its admins, an organization by the platform admin."""
    workspace = {d.action for d in _declared(table[("DELETE", "/api/workspaces/{workspace_id}")])}
    assert workspace == {"DeleteOrganizationWorkspace", "DeleteWorkspace"}
    org = {d.action for d in _declared(table[("DELETE", "/api/organizations/{org_id}")])}
    assert org == {"DeletePlatformOrganization"}
    assert LEVEL_OF["DeleteOrganizationWorkspace"] == "admin"
    assert TYPES_BY_NAME[TYPE_OF["DeletePlatformOrganization"]].placement == "platform"
