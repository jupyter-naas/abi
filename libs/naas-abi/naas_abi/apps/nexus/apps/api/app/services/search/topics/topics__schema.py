"""Search topics: the contract every topic query is held to.

A *topic* (Person, Organization, …) is one search "layer" of the Nexus search
page. It is data, not code: a handful of SPARQL SELECT templates whose
projected variables fill fixed UI slots. The page renders any topic the same
way — a results list, a detail header and detail sections — so adding a topic
never means adding UI.

Each template has a *role*. The role fixes which ``{{ placeholders }}`` the
template may use and which variables it must / may project:

=========  ===================  ==================  ===========================================
role       placeholders         required vars       optional vars
=========  ===================  ==================  ===========================================
results    q, limit, offset     uri, title          subtitle, snippet, image, score
header     uri                  title               subtitle, snippet, image, url  (+ any → facts)
section    uri, limit           title               item, subtitle, snippet, image, start, end, url, tags
image      uris                 uri, image
row        uris                 uri, value
=========  ===================  ==================  ===========================================

``image`` and ``row`` queries decorate a page of results: they run once per
page with ``{{ uris }}`` standing for that page's individuals (write
``VALUES ?uri { {{ uris }} }``). The image query gives each result its picture
(a person's portrait, an organization's logo); each row query is one labelled
line of metadata under a result (employer, office, people…), its values joined
when it binds several.

A section's ``tags`` is one string of newline-separated labels shown as chips
on its row (the skills and languages an experience developed): aggregate them
with ``GROUP_CONCAT(…; separator="\\n")``.

Placeholders are substituted server-side only, never by string formatting:
``{{ q }}`` is the *content* of a string literal (write it inside quotes),
``{{ uri }}`` becomes a validated ``<IRI>``, ``{{ limit }}``/``{{ offset }}`` integers.

Templates should not name a ``GRAPH``: they run against the union of the graphs
the workspace can read (see ``graph/adapters/secondary/scoped_store.py``).

Every name here (topic, role, slot) is meant to map 1:1 onto the generic search
ontology tracked in ``docs/adr/20261001_nexus-search-topics.md``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal

QueryRole = Literal["results", "header", "section", "image", "row"]
TopicSource = Literal["builtin", "override", "custom"]

TOPIC_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")

# Search page scopes that are not topics: the "All" view, Web and the Nexus
# features (web/src/lib/search-scopes.ts). A topic id must not shadow them.
RESERVED_TOPIC_IDS = frozenset(
    {
        "all",
        "web",
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
    }
)

# Scopes of the search page that are not topics and that a workspace admin can
# switch off: the Nexus features, and each web engine as "web.<engine>".
FEATURE_SCOPE_IDS = frozenset(RESERVED_TOPIC_IDS - {"all", "web"})
WEB_ENGINE_SCOPE_IDS = frozenset({"web.wikipedia", "web.duckduckgo"})
SWITCHABLE_SCOPE_IDS = FEATURE_SCOPE_IDS | WEB_ENGINE_SCOPE_IDS
# Until an admin changes anything, search covers the topics, Apps, Chats,
# Agents and the web engines; the other features start switched off.
DEFAULT_ENABLED_FEATURE_IDS = frozenset({"apps", "chat", "agents"})
DEFAULT_DISABLED_SCOPE_IDS = FEATURE_SCOPE_IDS - DEFAULT_ENABLED_FEATURE_IDS


@dataclass(frozen=True)
class RoleContract:
    placeholders: frozenset[str]
    required: frozenset[str]
    optional: frozenset[str]
    # Header queries surface every non-slot variable as a labelled fact.
    extra_as_facts: bool = False


ROLE_CONTRACTS: dict[str, RoleContract] = {
    "results": RoleContract(
        placeholders=frozenset({"q", "limit", "offset"}),
        required=frozenset({"uri", "title"}),
        optional=frozenset({"subtitle", "snippet", "image", "score"}),
    ),
    "header": RoleContract(
        placeholders=frozenset({"uri"}),
        required=frozenset({"title"}),
        optional=frozenset({"subtitle", "snippet", "image", "url"}),
        extra_as_facts=True,
    ),
    "section": RoleContract(
        placeholders=frozenset({"uri", "limit"}),
        required=frozenset({"title"}),
        optional=frozenset({"item", "subtitle", "snippet", "image", "start", "end", "url", "tags"}),
    ),
    "image": RoleContract(
        placeholders=frozenset({"uris"}),
        required=frozenset({"uri", "image"}),
        optional=frozenset(),
    ),
    "row": RoleContract(
        placeholders=frozenset({"uris"}),
        required=frozenset({"uri", "value"}),
        optional=frozenset(),
    ),
}


class SearchTopicError(Exception):
    """Base error for search topics."""


class SearchTopicNotFoundError(SearchTopicError):
    pass


class SearchTopicValidationError(SearchTopicError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class TopicSection:
    id: str
    label: str
    query: str
    empty_text: str = "Nothing recorded."
    # When set, a row's ?item opens in this topic's detail (e.g. experience → organization).
    link_topic: str | None = None


@dataclass(frozen=True)
class TopicResultRowDef:
    """One labelled line of metadata under each result, filled by a ``row`` query."""

    id: str
    label: str
    query: str


@dataclass(frozen=True)
class SearchTopic:
    id: str
    label: str
    plural_label: str
    description: str
    icon: str
    class_iri: str
    results_query: str
    header_query: str
    sections: tuple[TopicSection, ...] = ()
    # The picture of each result (``image`` role); empty: the results query's ?image.
    image_query: str = ""
    # Metadata lines under each result (``row`` role), in order.
    result_rows: tuple[TopicResultRowDef, ...] = ()
    # The tab that shows one individual: "Profile" for a person, "Card" for an organization.
    detail_label: str = "Details"
    # Graphs the topic reads, within what the workspace may read. Empty: every
    # graph the workspace can read (the default for every topic).
    graphs: tuple[str, ...] = ()
    enabled: bool = True
    order: int = 100
    source: TopicSource = "custom"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sections"] = [asdict(s) for s in self.sections]
        data["result_rows"] = [asdict(r) for r in self.result_rows]
        data["graphs"] = list(self.graphs)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, source: TopicSource | None = None) -> SearchTopic:
        sections = tuple(
            TopicSection(
                id=str(s["id"]),
                label=str(s["label"]),
                query=str(s["query"]),
                empty_text=str(s.get("empty_text") or "Nothing recorded."),
                link_topic=(str(s["link_topic"]) if s.get("link_topic") else None),
            )
            for s in data.get("sections") or []
        )
        return cls(
            id=str(data["id"]),
            label=str(data["label"]),
            plural_label=str(data.get("plural_label") or data["label"]),
            description=str(data.get("description") or ""),
            icon=str(data.get("icon") or "Search"),
            class_iri=str(data.get("class_iri") or ""),
            results_query=str(data["results_query"]),
            header_query=str(data["header_query"]),
            sections=sections,
            image_query=str(data.get("image_query") or ""),
            result_rows=tuple(
                TopicResultRowDef(id=str(r["id"]), label=str(r["label"]), query=str(r["query"]))
                for r in data.get("result_rows") or []
            ),
            detail_label=str(data.get("detail_label") or "Details"),
            graphs=tuple(dict.fromkeys(str(g) for g in data.get("graphs") or [] if str(g).strip())),
            enabled=bool(data.get("enabled", True)),
            order=int(data.get("order", 100)),
            source=source or data.get("source") or "custom",
        )

    def with_source(self, source: TopicSource) -> SearchTopic:
        return replace(self, source=source)


@dataclass(frozen=True)
class TopicResultRow:
    id: str
    label: str
    value: str


@dataclass(frozen=True)
class TopicResultItem:
    uri: str
    title: str
    subtitle: str | None = None
    snippet: str | None = None
    image: str | None = None
    score: float | None = None
    rows: list[TopicResultRow] = field(default_factory=list)


@dataclass(frozen=True)
class TopicResults:
    topic_id: str
    query: str
    items: list[TopicResultItem]
    has_more: bool
    sparql: str


@dataclass(frozen=True)
class TopicFact:
    key: str
    label: str
    value: str
    is_uri: bool = False


@dataclass(frozen=True)
class TopicSectionItem:
    title: str
    item: str | None = None
    subtitle: str | None = None
    snippet: str | None = None
    image: str | None = None
    start: str | None = None
    end: str | None = None
    url: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TopicSectionResult:
    id: str
    label: str
    empty_text: str
    link_topic: str | None
    items: list[TopicSectionItem]
    sparql: str
    error: str | None = None


@dataclass(frozen=True)
class TopicDetail:
    topic_id: str
    uri: str
    title: str
    subtitle: str | None = None
    snippet: str | None = None
    image: str | None = None
    url: str | None = None
    facts: list[TopicFact] = field(default_factory=list)
    sections: list[TopicSectionResult] = field(default_factory=list)
    header_sparql: str = ""
