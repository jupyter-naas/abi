"""Catalogs by publisher, with what the caller may grant."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.catalog import (
    ENGINE,
    NAAS_ABI,
    ActionCatalog,
    ActionSpec,
    CatalogError,
    ResourceType,
)
from naas_abi_core.services.iam.publishers import by_publisher
from naas_abi_core.services.iam.tests.iam_harness import (
    NEXUS,
    statement,
    workspace,
)

WS1 = workspace("ws-1")

CRM = ActionCatalog(
    service="acme_crm",
    version=1,
    module="acme.crm",
    resource_types=(ResourceType("deal", module_scope=True),),
    actions=(ActionSpec("ExportDeal", "read", ("deal",)),),
)


def test_a_catalog_names_its_publisher():
    assert NEXUS.publisher == ENGINE
    published = ActionCatalog.from_dict({**NEXUS.to_dict(), "publisher": NAAS_ABI})
    assert published.publisher == NAAS_ABI
    assert published.to_dict()["publisher"] == NAAS_ABI
    assert (
        ActionCatalog.from_dict(published.to_dict(stored=True), stored=True).publisher
        == NAAS_ABI
    )
    # The engine's is not written: nothing changes in what was stored before.
    assert "publisher" not in NEXUS.to_dict()
    # A module's catalog is its module's, whatever it says, and its form (what a
    # manifest hashes) does not carry it.
    assert CRM.publisher == "acme.crm"
    claimed = ActionCatalog.from_dict({**CRM.to_dict(), "publisher": NAAS_ABI})
    assert claimed.publisher == "acme.crm"
    assert "publisher" not in claimed.to_dict()


def test_a_catalog_publisher_is_never_empty():
    assert (
        ActionCatalog.from_dict({**NEXUS.to_dict(), "publisher": ""}).publisher
        == ENGINE
    )
    with pytest.raises(CatalogError):
        ActionCatalog(service="Bad", version=1, publisher=NAAS_ABI)


@pytest.fixture
def world(h):
    h.iam._register_catalog(module_scopes.CATALOG)
    h.iam._register_catalog(
        ActionCatalog.from_dict({**NEXUS.to_dict(), "publisher": NAAS_ABI})
    )
    with as_service_account("engine"):
        h.iam.register_catalog(CRM)
    h.register("ws-1")
    return h


MODULES = {"p": ("agent",), "m": ("app",), "acme.crm": ()}


def _view(h, user):
    with h.as_(user):
        grantable = h.iam.grantable(WS1)
    return by_publisher(
        h.iam.catalogs.all(),
        grantable,
        modules=MODULES,
        listable=h.iam.has_lister,
        scope=WS1,
    )


def test_a_user_holding_only_agent_a_gets_only_a(world):
    h = world
    user = h.user("bob")
    h.grant(
        user.id,
        statement(
            "Allow",
            ["module:UseAgent"],
            ["${scope}/module:agent/p/a"],
        ),
        statement("Allow", ["iam:CreatePolicy"], ["${scope}/iam:policy/*"]),
        scope=WS1,
    )
    view = _view(h, user)
    by_id = {p.id: p for p in view}
    # P with its agent A; nothing of M, of naas_abi or of the module's catalog.
    assert set(by_id) == {"engine", "p"}
    (agent,) = by_id["p"].types
    assert (agent.service, agent.type.name, agent.module) == ("module", "agent", "p")
    assert [a.spec.name for a in agent.actions] == ["UseAgent"]
    assert agent.actions[0].grantable.resources == ("${scope}/module:agent/p/a",)
    # The engine: only what they hold of IAM.
    assert [(t.service, t.type.name) for t in by_id["engine"].types] == [
        ("iam", "policy")
    ]


def test_publishers_come_engine_first_then_naas_abi_then_modules(world):
    h = world
    admin = h.user("admin")
    h.attach(roles.ADMIN, admin.id, WS1)
    h.grant(
        admin.id,
        statement(
            "Allow",
            ["module:*", "acme_crm:*"],
            ["${scope}/module:*", "${scope}/acme_crm:*"],
        ),
        scope=WS1,
    )
    view = _view(h, admin)
    assert [(p.id, p.kind) for p in view] == [
        ("engine", "engine"),
        ("naas_abi", "naas_abi"),
        ("acme.crm", "module"),
        ("m", "module"),
        ("p", "module"),
    ]
    by_id = {p.id: p for p in view}
    assert [(t.service, t.type.name) for t in by_id["acme.crm"].types] == [
        ("acme_crm", "deal")
    ]
    assert [t.type.name for t in by_id["m"].types] == ["app"]
    assert {t.service for t in by_id["naas_abi"].types} == {"nexus"}
    # Container types IAM lists itself; a type with no lister is not listed.
    workspace_type = next(
        t for t in by_id["naas_abi"].types if t.type.name == "workspace"
    )
    assert workspace_type.listed
    assert not by_id["acme.crm"].types[0].listed


def test_a_stranger_gets_no_publisher(world):
    h = world
    assert _view(h, h.user("stranger")) == []


def test_a_module_s_pattern_names_no_other_module_s_items(world):
    """``${scope}/module:agent/p/*`` reaches P's agents only: an id holds no
    step, so its ``*`` never reaches Q's (the type's names, not any glob)."""
    h = world
    user = h.user("bob")
    h.grant(
        user.id,
        statement("Allow", ["module:UseAgent"], ["${scope}/module:agent/p/*"]),
        scope=WS1,
    )
    with h.as_(user):
        grantable = h.iam.grantable(WS1)
    view = by_publisher(
        h.iam.catalogs.all(),
        grantable,
        modules={"p": ("agent",), "q": ("agent",)},
        listable=h.iam.has_lister,
    )
    assert [p.id for p in view] == ["p"]
    # Written for any container below the scope, it is still P's only.
    h.grant(
        user.id,
        statement("Allow", ["module:UseAgent"], ["${scope}/*/module:agent/p/*"]),
        scope=WS1,
    )
    with h.as_(user):
        grantable = h.iam.grantable(WS1)
    view = by_publisher(
        h.iam.catalogs.all(),
        grantable,
        modules={"p": ("agent",), "q": ("agent",)},
    )
    assert [p.id for p in view] == ["p"]


def test_a_type_lists_only_patterns_that_can_name_its_resources(world):
    """Under a type, only the patterns that can name one of its resources at
    the scope: a graph's pattern names no workspace, a workspace's no graph."""
    from naas_abi_core.services.iam.IAMPorts import GrantableAction, GrantableCatalog

    h = world
    held = (
        "${scope}",
        "${scope}/nexus:workspace/*",
        "${scope}/triple_store:graph/*",
    )
    grantable = [
        GrantableCatalog(
            "nexus", (GrantableAction("nexus:CreateWorkspace", held, ()),)
        ),
        GrantableCatalog(
            "triple_store", (GrantableAction("triple_store:Query", held, ()),)
        ),
    ]
    view = {p.id: p for p in by_publisher(h.iam.catalogs.all(), grantable, scope=WS1)}
    workspace = next(t for t in view["naas_abi"].types if t.type.name == "workspace")
    assert workspace.actions[0].grantable.resources == (
        "${scope}",
        "${scope}/nexus:workspace/*",
    )
    graph = next(t for t in view["engine"].types if t.type.name == "graph")
    # ``${scope}/nexus:workspace/*`` may hold graphs; ``${scope}`` is no graph.
    assert graph.actions[0].grantable.resources == (
        "${scope}/nexus:workspace/*",
        "${scope}/triple_store:graph/*",
    )


def test_a_step_of_another_type_names_nothing_of_a_type_without_a_search(
    world, monkeypatch
):
    """A name is its containers' steps, then its own: a pattern holding a literal
    step of a type that is no container, and not the type itself, names none of
    the type's resources. It is left out at once, as the search would: a holder
    of every type's pattern (an owner who is also the platform admin) is not
    made to wait for one search per type and pattern."""
    from naas_abi_core.services.iam import grants
    from naas_abi_core.services.iam.IAMPorts import GrantableAction, GrantableCatalog

    held = (
        "${scope}/*",
        "${scope}/model_registry:model/*",
        "${scope}/*/model_registry:model/*",
        "${scope}/nexus:workspace/*",
        "${scope}/triple_store:graph/*",
    )
    grantable = [
        GrantableCatalog(
            "triple_store", (GrantableAction("triple_store:Query", held, ()),)
        )
    ]
    searched: list[str] = []
    overlaps = grants.overlaps

    def spy(grant, others, within=grants.EVERYTHING, bounds=()):
        searched.append(grant)
        return overlaps(grant, others, within, bounds)

    monkeypatch.setattr(grants, "overlaps", spy)
    view = {
        p.id: p for p in by_publisher(world.iam.catalogs.all(), grantable, scope=WS1)
    }
    graph = next(t for t in view["engine"].types if t.type.name == "graph")
    assert graph.actions[0].grantable.resources == (
        "${scope}/*",
        "${scope}/nexus:workspace/*",
        "${scope}/triple_store:graph/*",
    )
    assert not [g for g in searched if "model_registry:model" in g]
