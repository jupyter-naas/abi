"""``/publishers``, ``/resources`` and ``/catalogs``: only what the caller may grant
or list at the scope, as the caller (core ``services/iam/AGENTS.md``, "Publishers
and listing")."""

from __future__ import annotations

from urllib.parse import quote

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.iam import listers
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.primary.iam_admin__primary_adapter__FastAPI_test import (  # noqa: E501, F401 - pytest fixtures
    audit,
    get,
    world,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.listing import FunctionLister, ListedResource
from naas_abi_core.services.iam.names import resource_name

WS1 = workspace_container("org-1", "ws-1")
ORG1 = org_container("org-1")
MODULES = {"p": ("agent",), "m": ("app",)}


@pytest.fixture
def listed(world, audit):  # noqa: F811 - imported pytest fixtures
    """The world, with graphs listed in ws-1 and ws-2, naas_abi's features and
    workspaces labelled, and modules P (an agent) and M (an app)."""
    iam = world.nexus.iam
    ws2 = world.nexus.workspace("org-1", "ws-2")
    graphs = [
        ListedResource(resource_name("triple_store", "graph", iri, container=where), iri)
        for where, iri in ((WS1, "http://g/sales"), (WS1, "http://g/hr"), (ws2, "http://g/ops"))
    ]
    iam.register_lister("triple_store", "graph", FunctionLister(lambda query: graphs))
    # The deployment enables chat and files, not code.
    enabled = ["chat", "files"]
    iam.register_lister(
        "nexus",
        "feature",
        FunctionLister(lambda query: listers.feature_items(query.container, enabled)),
    )
    iam.register_lister(
        "nexus",
        "workspace",
        FunctionLister(
            lambda query: [
                ListedResource(WS1, "ws-1", label="Sales"),
                ListedResource(ws2, "ws-2", label="Ops"),
            ]
        ),
    )

    async def modules():
        return MODULES

    previous = runtime.configure(
        lambda: IamAdminService(EngineIamGateway(), audit, modules=modules)
    )
    yield world
    runtime.configure(previous)


def _hold(at, user: str, scope: str, *statements: dict) -> None:
    at.nexus.user(user)
    with as_service_account("engine"):
        policy = at.nexus.iam.create_policy(
            f"{user} holds", {"version": "2026-10-13", "statements": list(statements)}
        )
        at.nexus.iam.attach_policy(policy.id, at.nexus.principal(user), scope)


def _resources(at, user: str, scope: str, service: str, type_name: str, **query):
    extra = "".join(f"&{k}={quote(str(v), safe='')}" for k, v in query.items())
    return get(
        at,
        f"/resources?scope={quote(scope, safe='')}&service={service}&type={type_name}{extra}",
        user,
    )


def test_a_workspace_admin_lists_the_graphs_of_their_workspace(listed):
    # An admin of ws-1 alone (``admin`` is an admin of org-1 too, so of ws-2).
    listed.nexus.grant("wsadmin", "admin", WS1)
    found = _resources(listed, "wsadmin", WS1, "triple_store", "graph")
    assert found.status_code == 200, found.text
    body = found.json()
    assert body["listed"] is True
    assert [i["id"] for i in body["items"]] == ["http://g/hr", "http://g/sales"]
    # Searched and paged.
    sales = _resources(listed, "wsadmin", WS1, "triple_store", "graph", q="SAL").json()
    assert [i["id"] for i in sales["items"]] == ["http://g/sales"]
    first = _resources(listed, "wsadmin", WS1, "triple_store", "graph", limit=1).json()
    assert len(first["items"]) == 1 and first["next_cursor"]
    rest = _resources(
        listed, "wsadmin", WS1, "triple_store", "graph", cursor=first["next_cursor"]
    ).json()
    assert [i["id"] for i in rest["items"]] == ["http://g/sales"]
    # Another workspace's graphs: none; a stranger: nothing at all.
    ws2 = workspace_container("org-1", "ws-2")
    assert _resources(listed, "wsadmin", ws2, "triple_store", "graph").json()["items"] == []
    at_org = _resources(listed, "wsadmin", ORG1, "triple_store", "graph").json()
    assert at_org["items"] == body["items"]
    stranger = _resources(listed, "stranger", WS1, "triple_store", "graph")
    assert stranger.status_code == 200 and stranger.json()["items"] == []


def test_organizations_and_workspaces_are_listed_to_whoever_may_list_them(listed):
    orgs = _resources(listed, "root", "abi:", "nexus", "organization").json()
    assert orgs["listed"] and ORG1 in [i["name"] for i in orgs["items"]]
    spaces = _resources(listed, "admin", ORG1, "nexus", "workspace").json()
    assert [(i["id"], i["label"]) for i in spaces["items"]] == [("ws-1", "Sales"), ("ws-2", "Ops")]
    assert _resources(listed, "stranger", "abi:", "nexus", "organization").json()["items"] == []
    assert _resources(listed, "stranger", ORG1, "nexus", "workspace").json()["items"] == []


def test_a_disabled_feature_is_listed_nowhere(listed):
    for user in ("root", "admin"):
        features = _resources(listed, user, WS1, "nexus", "feature").json()
        assert "code" not in [i["id"] for i in features["items"]]
    every = _resources(listed, "root", WS1, "nexus", "feature").json()
    assert sorted(i["id"] for i in every["items"]) == ["chat", "files"]


def test_a_type_with_no_lister_is_offered_as_wildcards_and_a_bad_one_refused(listed):
    unlisted = _resources(listed, "root", WS1, "triple_store", "view").json()
    assert unlisted["listed"] is False and unlisted["items"] == []
    assert _resources(listed, "root", WS1, "nope", "graph").status_code == 404
    assert _resources(listed, "root", "abi:o:w", "triple_store", "graph").status_code == 422


def test_a_user_holding_only_agent_a_gets_only_a(listed):
    _hold(
        listed,
        "builder",
        WS1,
        {
            "effect": "Allow",
            "actions": ["module:UseAgent"],
            "resources": ["${scope}/module:agent/p/a"],
        },
        {"effect": "Allow", "actions": ["iam:CreatePolicy"], "resources": ["${scope}/iam:policy/*"]},
    )
    publishers = get(listed, f"/publishers?scope={quote(WS1, safe='')}", "builder")
    assert publishers.status_code == 200, publishers.text
    by_id = {p["id"]: p for p in publishers.json()["publishers"]}
    assert set(by_id) == {"engine", "p"}
    (agent,) = by_id["p"]["types"]
    assert (agent["service"], agent["type"], agent["module"]) == ("module", "agent", "p")
    assert [(a["action"], a["resources"]) for a in agent["actions"]] == [
        ("module:UseAgent", ["${scope}/module:agent/p/a"])
    ]
    assert [(t["service"], t["type"]) for t in by_id["engine"]["types"]] == [("iam", "policy")]

    catalogs = get(listed, f"/catalogs?scope={quote(WS1, safe='')}", "builder")
    assert catalogs.status_code == 200, catalogs.text
    actions = {
        a["qualified"] for c in catalogs.json()["catalogs"] for a in c["actions"]
    }
    assert actions == {"module:UseAgent", "iam:CreatePolicy"}
    module = next(c for c in catalogs.json()["catalogs"] if c["service"] == "module")
    assert [t["name"] for t in module["resource_types"]] == ["agent"]


def test_publishers_come_in_order_with_what_each_type_lets_the_caller_grant(listed):
    publishers = get(listed, f"/publishers?scope={quote(WS1, safe='')}", "admin").json()
    ids = [p["id"] for p in publishers["publishers"]]
    # An admin of ws-1 holds no module scope: the engine and naas_abi only.
    assert ids == ["engine", "naas_abi"]
    naas_abi = publishers["publishers"][1]
    assert naas_abi["kind"] == "naas_abi"
    types = {t["type"]: t for t in naas_abi["types"]}
    assert types["workspace"]["listed"] and types["workspace"]["container"]
    graphs = next(
        t for t in publishers["publishers"][0]["types"] if t["service"] == "triple_store"
    )
    assert graphs["listed"] is True
    assert all(r.startswith("${scope}") for a in graphs["actions"] for r in a["resources"])
    assert get(listed, f"/publishers?scope={quote(WS1, safe='')}", "stranger").json()[
        "publishers"
    ] == []


def test_the_nexus_feature_lister_lists_only_enabled_features():
    flags = FeatureFlagsConfig(enabled_features=["chat", "code"])
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import enabled_feature_catalog

    enabled = enabled_feature_catalog(flags)
    items = listers.feature_items(WS1, enabled)
    assert [i.id for i in items] == ["chat", "code"]
    assert all(i.name.startswith(WS1 + "/nexus:feature/") for i in items)
    assert listers.feature_items("abi:", enabled) == []


def test_grantable_names_each_catalog_s_publisher_and_types(listed):
    found = get(listed, f"/grantable?scope={quote(WS1, safe='')}", "admin").json()
    by_service = {c["service"]: c for c in found["catalogs"]}
    assert by_service["nexus"]["publisher"] == "naas_abi"
    assert by_service["triple_store"]["publisher"] == "engine"
    query = next(a for a in by_service["triple_store"]["actions"] if a["action"] == "triple_store:Query")
    assert query["resource_types"] == ["graph"]


def test_within_a_parent_only_what_it_has_is_offered(listed):
    """A sub-policy of "O access" offers only what it allows: P's agents and chat,
    none of the data rights the admin holds besides; a parent the caller may not
    derive from is refused."""
    with as_service_account("engine"):
        o_access = listed.nexus.iam.create_policy(
            "O access",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["module:UseAgent"],
                        "resources": ["${scope}/module:agent/p/*"],
                    },
                    {
                        "effect": "Allow",
                        "actions": ["nexus:UseFeature"],
                        "resources": ["${scope}/nexus:feature/chat"],
                    },
                ],
            },
        )
        listed.nexus.iam.attach_policy(o_access.id, listed.nexus.principal("admin"), WS1)
    at = quote(WS1, safe="")
    alone = get(listed, f"/publishers?scope={at}", "admin").json()
    assert [p["id"] for p in alone["publishers"]] == ["engine", "naas_abi", "p"]

    within = get(listed, f"/publishers?scope={at}&parent={o_access.id}", "admin")
    assert within.status_code == 200, within.text
    by_id = {p["id"]: p for p in within.json()["publishers"]}
    assert list(by_id) == ["naas_abi", "p"]
    assert [
        (t["type"], [(a["action"], a["resources"]) for a in t["actions"]])
        for t in by_id["naas_abi"]["types"]
    ] == [("feature", [("nexus:UseFeature", ["${scope}/nexus:feature/chat"])])]
    assert [a["resources"] for a in by_id["p"]["types"][0]["actions"]] == [
        ["${scope}/module:agent/p/*"]
    ]
    catalogs = get(listed, f"/catalogs?scope={at}&parent={o_access.id}", "admin").json()
    assert {a["qualified"] for c in catalogs["catalogs"] for a in c["actions"]} == {
        "module:UseAgent",
        "nexus:UseFeature",
    }
    grantable = get(listed, f"/grantable?scope={at}&parent={o_access.id}", "admin").json()
    assert {c["service"] for c in grantable["catalogs"]} == {"module", "nexus"}

    listed.nexus.grant("wsadmin", "admin", WS1)
    refused = get(listed, f"/publishers?scope={at}&parent={o_access.id}", "wsadmin")
    assert refused.status_code == 403
    assert o_access.id in refused.json()["detail"]
    # Reading it is enough to edit a sub-policy of it, not to make a new one.
    _hold(
        listed,
        "wsadmin",
        None,
        {"effect": "Allow", "actions": ["iam:GetPolicy"], "resources": ["abi:iam:policy/*"]},
    )
    read = get(listed, f"/publishers?scope={at}&parent={o_access.id}", "wsadmin")
    assert read.status_code == 200, read.text
    new = get(listed, f"/publishers?scope={at}&parent={o_access.id}&derive=true", "wsadmin")
    assert new.status_code == 403
    assert o_access.id in new.json()["detail"]
    assert "attached to you or to one of your groups" in new.json()["detail"]
    # The O admin derives from it.
    derived = get(listed, f"/publishers?scope={at}&parent={o_access.id}&derive=true", "admin")
    assert derived.status_code == 200, derived.text


def test_a_type_lists_only_patterns_that_name_its_resources(listed):
    """At a workspace: no Organizations type (none sits in a workspace), and
    Workspaces lists none of the organisation's forms."""
    listed.nexus.grant("wsadmin", "admin", WS1)
    found = get(listed, f"/publishers?scope={quote(WS1, safe='')}", "wsadmin").json()
    naas_abi = next(p for p in found["publishers"] if p["id"] == "naas_abi")
    types = {t["type"]: t for t in naas_abi["types"]}
    assert "organization" not in types
    for action in types["workspace"]["actions"]:
        assert all("nexus:organization" not in r for r in action["resources"]), action["resources"]
