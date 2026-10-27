"""The set grammar, matching, intersection and containment (``sets.py``)."""

from __future__ import annotations

import pytest

from naas_abi_core.services.iam import module_scopes, sets
from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ActionSpec,
    CatalogRegistry,
    ResourceType,
)
from naas_abi_core.services.iam.IAMPorts import ScopeSet
from naas_abi_core.services.iam.names import parse_resource_name

NEXUS = ActionCatalog(
    service="nexus",
    version=1,
    resource_types=(ResourceType("feature"), ResourceType("workspace")),
    actions=(
        ActionSpec("UseFeature", "read", ("feature",)),
        ActionSpec("GetWorkspace", "read", ("workspace",)),
    ),
)
PEOPLE = module_scopes.module_catalog(
    {
        "resource_types": [{"name": "report", "id": "opaque"}],
        "actions": [
            {"name": "ExportReport", "level": "write", "resource_types": ["report"]},
            {"name": "ReadReport", "level": "read", "resource_types": ["report"]},
        ],
    },
    "acme.people",
)


@pytest.fixture
def catalogs() -> CatalogRegistry:
    registry = CatalogRegistry()
    for catalog in (module_scopes.CATALOG, NEXUS, PEOPLE):
        registry.register(catalog)
    return registry


def _name(rest: str) -> object:
    return parse_resource_name(f"abi:org-1:ws-1:{rest}")


def test_items_are_checked_and_sorted():
    modules, features = sets.normalize(
        [
            "acme.people",
            "agent/naas_abi/Abi",
            "acme_people:ExportReport",
            "acme.people",
        ],
        ["chat", "files"],
    )
    assert modules == ("acme.people", "acme_people:ExportReport", "agent/naas_abi/Abi")
    assert features == ("chat", "files")
    with pytest.raises(sets.SetValidationError) as refused:
        sets.normalize(["tool/naas_abi/x", "a b", ""], ["Chat"])
    message = str(refused.value)
    for bad in ("tool/naas_abi/x", "'a b'", "''", "'Chat'"):
        assert bad in message
    assert sets.normalize(None, None) == (None, None)


def test_a_set_bounds_module_scopes_and_features_only(catalogs):
    assert sets.bounded(catalogs, "module", "agent")
    assert sets.bounded(catalogs, "acme_people", "report")
    assert sets.bounded(catalogs, "nexus", "feature")
    assert not sets.bounded(catalogs, "nexus", "workspace")
    assert not sets.bounded(catalogs, "triple_store", "graph")


def test_what_a_set_allows(catalogs):
    whole = ScopeSet("org-1", "ws-1", modules=("acme.people",), features=("chat",))
    one = ScopeSet("org-1", "ws-1", modules=("agent/naas_abi/Abi",), features=())
    action_only = ScopeSet("org-1", "ws-1", modules=("acme_people:ReadReport",))
    every_agent = ScopeSet("org-1", "ws-1", modules=("agent/acme.people/*",))
    agent = _name("module:agent/acme.people/Recruiter")
    abi = _name("module:agent/naas_abi/Abi")
    report = _name("acme_people:report/q3")
    chat = _name("nexus:feature/chat")

    assert sets.allows(whole, catalogs, "module:UseAgent", agent)
    assert not sets.allows(whole, catalogs, "module:UseAgent", abi)
    assert sets.allows(whole, catalogs, "acme_people:ExportReport", report)
    assert sets.allows(whole, catalogs, "nexus:UseFeature", chat)
    assert sets.allows(one, catalogs, "module:UseAgent", abi)
    assert not sets.allows(one, catalogs, "module:UseAgent", agent)
    assert not sets.allows(one, catalogs, "nexus:UseFeature", chat)
    assert sets.allows(action_only, catalogs, "acme_people:ReadReport", report)
    assert not sets.allows(action_only, catalogs, "acme_people:ExportReport", report)
    assert sets.allows(every_agent, catalogs, "module:UseAgent", agent)
    assert not sets.allows(
        every_agent, catalogs, "module:OpenApp", _name("module:app/acme.people/X")
    )
    # A part left unrecorded is everything.
    assert sets.allows(action_only, catalogs, "nexus:UseFeature", chat)


def test_a_workspace_set_within_its_orgs():
    org = ScopeSet(
        "org-1", modules=("acme.people", "agent/naas_abi/Abi"), features=("chat",)
    )
    within = ScopeSet(
        "org-1",
        "ws-1",
        modules=(
            "agent/acme.people/Recruiter",
            "acme_people:ExportReport",
            "agent/naas_abi/Abi",
        ),
        features=("chat",),
    )
    assert sets.outside(within, org) == []
    by_type = ScopeSet("org-1", modules=("workflow/crm/*",))
    assert (
        sets.outside(ScopeSet("org-1", "ws-1", modules=("workflow/crm/Sync",)), by_type)
        == []
    )
    assert sets.outside(
        ScopeSet("org-1", "ws-1", modules=("agent/crm/Sync",)), by_type
    ) == ["agent/crm/Sync"]
    wider = ScopeSet(
        "org-1", "ws-1", modules=("naas_abi", "market"), features=("chat", "files")
    )
    assert sorted(sets.outside(wider, org)) == ["feature files", "market", "naas_abi"]
    # Unrecorded parts follow the org's; an org with none bounds nothing.
    assert sets.outside(ScopeSet("org-1", "ws-1"), org) == []
    assert sets.outside(wider, None) == []
    assert sets.outside(wider, ScopeSet("org-1")) == []


def test_the_effective_set_is_the_intersection():
    org = ScopeSet(
        "org-1",
        modules=("acme.people", "agent/naas_abi/Abi"),
        features=("chat", "files"),
    )
    workspace = ScopeSet(
        "org-1",
        "ws-1",
        modules=("agent/acme.people/Recruiter", "naas_abi"),
        features=("chat", "maps"),
    )
    effective = sets.intersect(org, workspace)
    assert effective.modules == ("agent/acme.people/Recruiter", "agent/naas_abi/Abi")
    assert effective.features == ("chat",)
    assert sets.intersect(org, None).modules == org.modules
    assert sets.intersect(None, workspace).features == workspace.features
    assert sets.intersect(None, None).modules is None


def test_held_patterns_say_what_the_set_lets_anyone_grant(catalogs):
    scope = "abi:org-1:ws-1"
    found = ScopeSet(
        "org-1",
        "ws-1",
        modules=("acme.people", "app/naas_abi/files viewer", "app/crm/*"),
        features=("chat",),
    )
    assert sets.held_patterns(found, catalogs, "module:UseAgent", scope) == (
        "abi:org-1:ws-1:module:agent/acme.people/*",
    )
    assert sets.held_patterns(found, catalogs, "module:OpenApp", scope) == (
        "abi:org-1:ws-1:module:app/acme.people/*",
        "abi:org-1:ws-1:module:app/naas_abi/files%20viewer",
        "abi:org-1:ws-1:module:app/crm/*",
    )
    assert sets.held_patterns(found, catalogs, "acme_people:ExportReport", scope) == (
        "abi:org-1:ws-1:acme_people:report/*",
    )
    assert sets.held_patterns(found, catalogs, "nexus:UseFeature", scope) == (
        "abi:org-1:ws-1:nexus:feature/chat",
    )
    # Not bounded: anything.
    assert sets.held_patterns(found, catalogs, "nexus:GetWorkspace", scope) == ("*",)
    assert sets.held_patterns(found, catalogs, "triple_store:Query", scope) == ("*",)


def test_names_of_a_set():
    assert sets.read_resource("org-1") == "abi:org-1:-:iam:set/org-1"
    assert sets.read_resource("org-1", "ws-1") == "abi:org-1:ws-1:iam:set/ws-1"
    assert sets.write_resource("org-1") == "abi:%2A:%2A:iam:set/org-1"
    assert sets.write_resource("org-1", "ws-1") == "abi:org-1:%2A:iam:set/ws-1"
    parse_resource_name(sets.write_resource("org-1", "ws-1"))


def test_wildcards_of_every_module(catalogs):
    every = ScopeSet(
        "org-1", "ws-1", modules=("agent/acme.people/Recruiter", "app/*/*", "*:*")
    )
    assert sets.allows(
        every, catalogs, "module:OpenApp", _name("module:app/later.module/X")
    )
    assert sets.allows(
        every, catalogs, "acme_people:ExportReport", _name("acme_people:report/q3")
    )
    assert not sets.allows(
        every, catalogs, "module:UseAgent", _name("module:agent/acme.people/Other")
    )
    one_service = ScopeSet("org-1", "ws-1", modules=("acme_people:*",))
    assert sets.allows(
        one_service, catalogs, "acme_people:ReadReport", _name("acme_people:report/q3")
    )
    # Within: a wildcard holds its own kind only.
    assert sets.within(("app/*/*",), "app/crm/Sales")
    assert sets.within(("app/*/*",), "app/crm/*")
    assert not sets.within(("app/crm/*",), "app/*/*")
    assert sets.within(("*:*",), "acme_people:*")
    assert sets.within(("acme.people",), "acme_people:*")
    assert not sets.within(("acme_people:*",), "*:*")
    with pytest.raises(sets.SetValidationError):
        sets.normalize(["agent/*/Recruiter", "*:Export"], None)


def test_a_whole_module_meets_a_wildcard_of_every_module():
    org = ScopeSet("org-1", modules=("people", "crm_x:Sync"))
    workspace = ScopeSet(
        "org-1", "ws-1", modules=("agent/people/A", "workflow/*/*", "*:*")
    )
    effective = sets.intersect(org, workspace)
    assert effective.modules == (
        "agent/people/A",
        "crm_x:Sync",
        "people:*",
        "workflow/people/*",
    )


def test_held_patterns_of_every_module(catalogs):
    found = ScopeSet("org-1", "ws-1", modules=("app/*/*", "*:*"))
    scope = "abi:org-1:ws-1"
    assert sets.held_patterns(found, catalogs, "module:OpenApp", scope) == (
        "abi:org-1:ws-1:module:app/*",
    )
    assert sets.held_patterns(found, catalogs, "module:UseAgent", scope) == ()
    assert sets.held_patterns(found, catalogs, "acme_people:ExportReport", scope) == (
        "abi:org-1:ws-1:acme_people:report/*",
    )
