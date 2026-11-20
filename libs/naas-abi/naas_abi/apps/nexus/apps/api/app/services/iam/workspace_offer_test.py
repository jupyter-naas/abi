"""A workspace's access policy is an allow-list of what it offers
(``workspace_offer``): a module offered in W is reachable in W and nowhere else, and
a module added to the platform reaches no workspace until it is added. A real IAM:
nothing about who may do what is mocked."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.iam import container_defaults
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    NOTHING_SID,
    nothing_document,
    plan_and_apply,
    sync,
    widen_offer,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    Offer,
    in_offer_form,
    item_pattern,
    offer_document,
    offer_from_seed,
    offer_of,
    with_offer,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import module_scopes

W = workspace_container("acme", "w")
W2 = workspace_container("acme", "w2")


def _scope(type_name: str, module: str, name: str, container: str) -> str:
    return module_scopes.scope_resource(type_name, module, name, container=container)


# -- the document --------------------------------------------------------------------------


def test_an_offer_is_written_in_sections_and_read_back():
    offer = Offer.of(
        agents=[("acme.sales", "SalesAgent")],
        apps=[("acme.sales", "board")],
        modules=["shared.search"],
        features=["chat", "files"],
    )
    document = offer_document(offer)
    sids = [s["sid"] for s in document["statements"]]
    assert sids == ["OfferAgents", "OfferApps", "OfferWorkflows", "OfferPipelines", "OfferFeatures"]
    agents = document["statements"][0]
    assert agents["actions"] == ["module:UseAgent"]
    # One item by name, a shared module whole: never every module.
    assert agents["resources"] == [
        "${scope}/module:agent/acme.sales/SalesAgent",
        "${scope}/module:agent/shared.search/*",
    ]
    assert document["statements"][2]["actions"] == ["module:RunWorkflow", "module:ReadWorkflowRuns"]
    assert offer_of(document) == offer
    assert in_offer_form(document)
    assert offer.offers("workflows", "shared.search", "nightly")
    assert not offer.offers("agents", "acme.sales", "OtherAgent")


def test_nothing_offered_is_the_nothing_document_and_other_statements_are_kept():
    assert offer_document(Offer()) == nothing_document()
    assert in_offer_form(nothing_document())
    older = {
        "version": "2026-10-13",
        "statements": [
            {
                "sid": "Older",
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": ["${scope}/module:agent/*"],
            },
            {
                "sid": "TurnedOff",
                "effect": "Deny",
                "actions": ["module:UseAgent"],
                "resources": ["${scope}/module:agent/other/X"],
            },
        ],
    }
    # A ceiling of an older version is no allow-list: the access migration's.
    assert not in_offer_form(older)
    written = with_offer(older, Offer.of(features=["chat"]))
    assert [s["sid"] for s in written["statements"]] == ["Older", "TurnedOff", "OfferFeatures"]
    assert with_offer(nothing_document(), Offer()) == nothing_document()
    assert item_pattern("apps", "a b", "x/y") == "${scope}/module:app/a%20b/x%2Fy"


def test_the_seed_resolves_its_agents_and_names_what_it_cannot():
    offer, unresolved = offer_from_seed(
        agents=["acme.sales SalesAgent", "gone.module GoneAgent"],
        apps=["acme.sales:board"],
        modules=["shared.search"],
        features=["chat"],
        resolve_agent=lambda ref: ("acme.sales", "SalesAgent") if ref.startswith("acme") else None,
        resolve_app=lambda app_id: ("acme.sales", "board"),
    )
    assert unresolved == ["gone.module GoneAgent"]
    assert offer.agents == {("acme.sales", "SalesAgent"), ("shared.search", "*")}
    assert offer.apps == {("acme.sales", "board"), ("shared.search", "*")}
    assert offer.features == {"chat"}


# -- in IAM ----------------------------------------------------------------------------------


@pytest.fixture
def world():
    nexus = NexusIam(FeatureFlagsConfig(enabled_features=["chat"]), features_with_roles=False)
    nexus.workspace("acme", "w")
    nexus.workspace("acme", "w2")
    for scope in (W, W2):
        nexus.grant("olivia", "admin", scope)
    with nexus.installed():
        yield nexus


def _uses(nexus: NexusIam, user: str, resource: str, action: str = "module:UseAgent") -> bool:
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize(action, resource).allowed


def _make(nexus: NexusIam, offers: dict[str, Offer]):
    """Acme, W and W2 as the start-up pass makes them, W2 with no seed."""
    workspaces = {"w": ("acme", "W"), "w2": ("acme", "W2")}
    with as_service_account("api"):
        made, report = plan_and_apply(nexus.iam, {"acme": "Acme"}, workspaces, {}, offers)
    records = {record.container: record for record in made}
    holders = container_defaults.holders_by_container(nexus.iam)
    with as_service_account("api"):
        for record in made:
            sync(nexus.iam, record, holders.get(record.container, {}))
    return records, report


def test_a_module_turned_on_in_w_only_is_reachable_in_w_not_in_w2(world):
    seeded = Offer.of(modules=["acme.sales"], features=["chat"])
    records, report = _make(world, {"w": seeded})
    assert not report.failed
    # The seed is in W's allow-list and its organization's, which bounds it.
    assert set(report.offered) == {org_container("acme")}
    with as_service_account("api"):
        org_access = world.iam.get_policy(records[org_container("acme")].access_policy_id)
        w_access = world.iam.get_policy(records[W].access_policy_id)
        w2_access = world.iam.get_policy(records[W2].access_policy_id)
    assert offer_of(org_access.document) == seeded
    assert offer_of(w_access.document) == seeded
    assert [s.sid for s in w2_access.document.statements] == [NOTHING_SID]

    sales = ("agent", "acme.sales", "SalesAgent")
    assert _uses(world, "olivia", _scope(*sales, W))
    assert not _uses(world, "olivia", _scope(*sales, W2))
    # The module's workflows come with it, in W only.
    assert _uses(
        world, "olivia", _scope("workflow", "acme.sales", "nightly", W), "module:RunWorkflow"
    )
    # A module added to the platform reaches no workspace until it is offered.
    assert not _uses(world, "olivia", _scope("agent", "new.module", "NewAgent", W))
    # The feature W offers is used there, nowhere else.
    chat = "nexus:UseFeature"
    assert _uses(world, "olivia", nexus_resource("feature", container=W, id="chat"), chat)
    assert not _uses(world, "olivia", nexus_resource("feature", container=W2, id="chat"), chat)

    # Offered in W2 later: reachable there too.
    with as_service_account("api"):
        assert widen_offer(
            world.iam, records[W2].access_policy_id, Offer.of(modules=["acme.sales"])
        )
        # Adding what is offered already changes nothing.
        assert not widen_offer(world.iam, records[W].access_policy_id, seeded)
    assert _uses(world, "olivia", _scope(*sales, W2))


def test_a_reseed_adds_the_seeds_instances_never_its_features(world):
    records, _report = _make(world, {"w": Offer.of(agents=[("acme.sales", "SalesAgent")])})
    known = dict(records)
    again = Offer.of(
        agents=[("acme.sales", "SalesAgent"), ("acme.sales", "Helper")], features=["chat"]
    )
    with as_service_account("api"):
        _made, report = plan_and_apply(
            world.iam,
            {"acme": "Acme"},
            {"w": ("acme", "W"), "w2": ("acme", "W2")},
            known,
            {"w": again},
        )
        w_access = world.iam.get_policy(records[W].access_policy_id)
        org_access = world.iam.get_policy(records[org_container("acme")].access_policy_id)
    assert set(report.offered) == {W, org_container("acme")}
    assert offer_of(w_access.document).agents == again.agents
    assert offer_of(w_access.document).features == frozenset()
    assert offer_of(org_access.document).features == {"chat"}
