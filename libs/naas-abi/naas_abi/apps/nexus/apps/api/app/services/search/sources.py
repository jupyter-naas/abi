"""The sources a search reads, as the workspace's offer names them
(``search_source/<id>``, section ``OfferSearchSources`` of "<W> access").

A feature's items (``chat``: conversation titles...) or a web engine (``web.<engine>``:
the query leaves Nexus). The web page lists the same ids (``lib/search-scopes.ts``).
A workspace's topics are its own content, not a source of the offer: a topic switched
off is refused by the topics' routes.
"""

from __future__ import annotations

from collections.abc import Iterable

# The features the search reads, in the page's order.
FEATURE_SOURCES: tuple[str, ...] = (
    "apps",
    "chat",
    "files",
    "documents",
    "slides",
    "sheets",
    "datasets",
    "ontology",
    "graph",
    "maps",
    "agents",
)
# The engines ``POST /api/search/web`` implements.
WEB_ENGINES: tuple[str, ...] = ("wikipedia", "duckduckgo")
WEB_PREFIX = "web."


def web_source(engine: str) -> str:
    return f"{WEB_PREFIX}{engine}"


ALL_SOURCES: tuple[str, ...] = (*FEATURE_SOURCES, *(web_source(e) for e in WEB_ENGINES))


# Until a workspace chose, its search covers Apps, Chats, Agents and the web engines;
# the other features start switched off (``topics__schema.DEFAULT_ENABLED_FEATURE_IDS``).
DEFAULT_FEATURE_SOURCES: frozenset[str] = frozenset({"apps", "chat", "agents"})


def default_sources(switched_off: Iterable[str] | None = None) -> frozenset[str]:
    """What a workspace offers to its search: every source but those switched off
    (the ``disabled_scopes`` Settings › Search kept before the offer); with no choice
    recorded (None), the defaults."""
    if switched_off is None:
        off = set(FEATURE_SOURCES) - DEFAULT_FEATURE_SOURCES
    else:
        off = {str(s) for s in switched_off}
    return frozenset(s for s in ALL_SOURCES if s not in off)
