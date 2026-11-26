"""Access levels: Nexus features and core services kept apart; a cap (Deny) or a grant
(Allow) read back as the level it was written with; the rest of a policy kept."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam import access_levels as levels

DOC = {"version": "2026-10-13", "statements": []}


def test_features_and_core_services_are_apart():
    features = {g.name for g in levels.groups("feature")}
    services = {g.name for g in levels.groups("service")}
    assert {"graph", "files", "chat"} <= features
    assert {"triple_store", "object_storage", "vector_store", "secret"} <= services
    assert all(a.action.startswith("nexus:") for g in levels.groups("feature") for a in g.actions)
    assert not any(
        a.action.startswith("nexus:") for g in levels.groups("service") for a in g.actions
    )
    # A workspace names what it holds: no pattern beyond ${scope}.
    assert all(r.startswith("${scope}/") for g in levels.groups() for r in g.resources())


def test_a_cap_denies_what_is_above_its_level_and_reads_back():
    doc = levels.with_levels(DOC, "cap", {"feature:graph": "read", "service:triple_store": "none"})
    graph, store = doc["statements"]
    assert graph["effect"] == "Deny" and "nexus:CreateView" in graph["actions"]
    assert "nexus:GetView" not in graph["actions"]
    assert store["sid"] == "AccessLevelCap2" and store["resources"] == ["${scope}/triple_store:*"]
    read = levels.levels_of(doc, "cap")
    assert read["feature:graph"] == "read" and read["service:triple_store"] == "none"
    # No cap: the highest level.
    assert read["feature:chat"] == levels.group("feature:chat").choices("cap")[-1]


def test_a_grant_allows_up_to_its_level_and_reads_back():
    doc = levels.with_levels(DOC, "grant", {"service:secret": "write"})
    (statement,) = doc["statements"]
    assert statement["effect"] == "Allow" and statement["sid"] == "AccessLevelGrant"
    assert levels.levels_of(doc, "grant")["service:secret"] == "write"
    assert levels.levels_of(doc, "grant")["service:vector_store"] == "none"


def test_rewriting_keeps_the_other_statements():
    other = {
        "sid": "OfferFeatures",
        "effect": "Allow",
        "actions": ["nexus:UseFeature"],
        "resources": ["${scope}/nexus:feature/chat"],
    }
    doc = levels.with_levels({**DOC, "statements": [other]}, "cap", {"feature:graph": "read"})
    doc = levels.with_levels(doc, "cap", {"feature:graph": "write"})
    assert doc["statements"] == [other]


def test_none_denies_the_feature_itself_even_one_with_no_action_of_its_own():
    slides = levels.group("feature:slides")
    assert slides is not None and slides.choices("cap") == ["none", "read"]
    doc = levels.with_levels(DOC, "cap", {"feature:slides": "none", "feature:graph": "read"})
    denied = {
        a
        for s in doc["statements"]
        for a in s["actions"]
        if "${scope}/nexus:feature/slides" in s["resources"]
    }
    assert denied == {"nexus:UseFeature"}
    read = levels.levels_of(doc, "cap")
    # Each feature's UseFeature is told apart by the feature it names.
    assert read["feature:slides"] == "none" and read["feature:graph"] == "read"
    assert read["feature:documents"] == "read"
