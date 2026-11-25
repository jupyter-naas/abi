"""What the move into the offer writes for each access policy (``search_sources_offer``)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.iam.search_sources_offer import (
    has_sources_section,
    sources_for,
    with_sources,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_document
from naas_abi.apps.nexus.apps.api.app.services.search.sources import ALL_SOURCES

W = workspace_container("acme", "ws-1")


def test_an_organization_offers_every_source():
    assert sources_for(org_container("acme"), {}) == frozenset(ALL_SOURCES)


def test_a_workspace_keeps_what_it_chose_or_else_the_defaults():
    chose = sources_for(W, {"ws-1": ["web.duckduckgo", "chat"]})
    assert "chat" not in chose and "web.duckduckgo" not in chose and "files" in chose
    # Never chose: Apps, Chats, Agents and the web engines, as the page showed.
    assert sources_for(W, {}) == {"apps", "chat", "agents", "web.wikipedia", "web.duckduckgo"}
    # Chose to switch nothing off: everything.
    assert sources_for(W, {"ws-1": []}) == frozenset(ALL_SOURCES)


def test_the_section_is_added_and_every_other_statement_kept():
    older = {
        "version": "2026-10-13",
        "statements": [
            {
                "sid": "Modules",
                "effect": "Allow",
                "actions": ["module:*"],
                "resources": ["${scope}:module:agent/*"],
            },
            *offer_document(Offer.of(features=["search"]))["statements"],
        ],
    }
    assert not has_sources_section(older)
    written = with_sources(older, ["chat"])
    assert [s["sid"] for s in written["statements"]] == [
        "Modules",
        "OfferFeatures",
        "OfferSearchSources",
    ]
    assert has_sources_section(written)
