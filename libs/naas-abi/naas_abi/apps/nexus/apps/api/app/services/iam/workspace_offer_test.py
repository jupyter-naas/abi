"""A workspace's access policy is an allow-list of what it offers
(``workspace_offer``): a module offered in W is reachable in W and nowhere else, and
a module added to the platform reaches no workspace until it is added. A real IAM:
nothing about who may do what is mocked."""

from __future__ import annotations

from dataclasses import replace

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
    OrgFiles,
    in_offer_form,
    instances_only,
    item_pattern,
    offer_document,
    offer_from_seed,
    offer_of,
    offer_section,
    with_offer,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.policy import MAX_PATTERNS, parse_policy_document

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


def test_a_section_past_the_pattern_limit_is_written_in_parts_and_read_back():
    agents = [("acme.sales", f"Agent{i:03}") for i in range(2 * MAX_PATTERNS + 50)]
    offer = Offer.of(agents=agents, features=["chat"])
    document = offer_document(offer)
    sids = [s["sid"] for s in document["statements"]]
    assert sids == ["OfferAgents", "OfferAgents2", "OfferAgents3", "OfferFeatures"]
    assert [len(s["resources"]) for s in document["statements"]] == [100, 100, 50, 1]
    parse_policy_document(document)
    assert offer_of(document) == offer
    assert in_offer_form(document)
    # A smaller offer replaces every part.
    smaller = Offer.of(agents=agents[:3])
    assert [s["sid"] for s in with_offer(document, smaller)["statements"]] == ["OfferAgents"]
    assert offer_section("OfferAgents3") == "OfferAgents"
    for sid in ("OfferAgents1", "OfferAgents02", "OfferAgentsX", "Older", None):
        assert offer_section(sid) is None


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


def test_a_workspace_offering_more_agents_than_one_statement_holds_reaches_each(world):
    agents = [("acme.sales", f"Agent{i:03}") for i in range(MAX_PATTERNS + 50)]
    records, report = _make(world, {"w": Offer.of(agents=agents)})
    assert not report.failed
    with as_service_account("api"):
        w_access = world.iam.get_policy(records[W].access_policy_id)
    assert [s.sid for s in w_access.document.statements] == ["OfferAgents", "OfferAgents2"]
    for module, name in (agents[0], agents[-1]):
        assert _uses(world, "olivia", _scope("agent", module, name, W))
        assert not _uses(world, "olivia", _scope("agent", module, name, W2))


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


def test_search_sources_are_a_section_of_their_own():
    offer = Offer.of(features=["search"], search_sources=["chat", "web.wikipedia"])
    document = offer_document(offer)
    assert [s["sid"] for s in document["statements"]] == ["OfferFeatures", "OfferSearchSources"]
    sources = document["statements"][1]
    assert sources["actions"] == ["nexus:UseSearchSource"]
    assert sources["resources"] == [
        "${scope}/nexus:search_source/chat",
        "${scope}/nexus:search_source/web.wikipedia",
    ]
    assert offer_of(document) == offer
    assert in_offer_form(document)
    assert offer_section("OfferSearchSources2") == "OfferSearchSources"
    assert Offer.of(search_sources=["chat"]).merged(
        Offer.of(search_sources=["maps"])
    ).search_sources == {"chat", "maps"}
    assert Offer.of(search_sources=["chat", "maps"]).without(
        Offer.of(search_sources=["maps"])
    ).search_sources == {"chat"}
    assert not Offer.of(search_sources=["chat"]).is_empty()


def test_ontologies_are_a_section_named_by_their_refs():
    offer = Offer.of(ontologies=["adqcc:AdqccOntology.ttl", "bfo:bfo-core.ttl"])
    document = offer_document(offer)
    assert [s["sid"] for s in document["statements"]] == ["OfferOntologies"]
    assert document["statements"][0]["actions"] == ["nexus:UseOntology"]
    assert offer_of(document) == offer
    many = Offer.of(ontologies=[f"m:o{i:03}.ttl" for i in range(MAX_PATTERNS + 5)])
    assert [s["sid"] for s in offer_document(many)["statements"]] == [
        "OfferOntologies",
        "OfferOntologies2",
    ]
    assert offer_of(offer_document(many)) == many


def test_the_files_given_outside_the_workspace_are_sections_of_the_offer():
    """Organization, Platform and System Files are given sections: absolute names (no
    ``${scope}``), each its Nexus half and its object storage half, read back as modes."""
    offer = Offer.of(
        features=["files"],
        org_files=OrgFiles("acme", "write"),
        platform_files="read",
        system_files="read",
    )
    document = offer_document(offer)
    assert [s["sid"] for s in document["statements"]] == [
        "OfferFeatures",
        "GivenOrgFiles",
        "GivenOrgFiles2",
        "GivenPlatformFiles",
        "GivenPlatformFiles2",
        "GivenSystemFiles",
        "GivenSystemFiles2",
    ]
    given = [s for s in document["statements"] if s["sid"].startswith("Given")]
    assert all("${" not in r for s in given for r in s["resources"])
    org = given[0]
    assert org["actions"] == [
        "nexus:ListOrgFiles",
        "nexus:GetOrgFile",
        "nexus:PutOrgFile",
        "nexus:DeleteOrgFile",
    ]
    assert org["resources"] == [
        "abi:nexus:organization/acme/nexus:file/organization",
        "abi:nexus:organization/acme/nexus:file/organization/*",
    ]
    assert given[3]["resources"] == [
        "abi:object_storage:object/naas_abi/platform-drive",
        "abi:object_storage:object/naas_abi/platform-drive/*",
    ]
    assert "object_storage:PutObject" not in given[3]["actions"]
    assert offer_of(document) == offer
    assert in_offer_form(document)
    assert offer_section("GivenPlatformFiles2") == "GivenPlatformFiles"
    parse_policy_document(document)
    # The wider mode wins a merge; ``without`` takes a section given as wide.
    assert (
        Offer.of(platform_files="read").merged(Offer.of(platform_files="write")).platform_files
        == "write"
    )
    assert Offer.of(platform_files="read").without(Offer.of(platform_files="write")) == Offer()
    assert not Offer.of(system_files="read").is_empty()
    # Rewriting the sections keeps the rest; a section turned off is gone.
    narrowed = with_offer(document, replace(offer_of(document), platform_files=None))
    assert offer_of(narrowed) == replace(offer, platform_files=None)
    assert not any(s["sid"].startswith("GivenPlatformFiles") for s in narrowed["statements"])
    # System Files is read only.
    with pytest.raises(ValueError, match="System Files"):
        offer_document(Offer.of(system_files="write"))
    # A re-seed adds instances, never a given section.
    assert instances_only(offer).is_empty()
