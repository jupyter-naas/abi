"""Domain model for the graph query compiler (AUDIT §7b.1).

Frozen dataclasses mirroring the ``ViewQuerySpec`` (the compiled form of the authoring
pipeline). These are Pydantic-free on purpose: the primary adapter converts its transport
models into these at the boundary, and the compiler consumes only these — so the compiler
stays a pure, unit-testable function with no framework coupling.

Collections are tuples (immutable) so a spec is hashable / cache-keyable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Multihop path ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Hop:
    predicate: str
    direction: str = "out"  # "out": ?from p ?to | "in": ?to p ?from
    quantifier: str = "one"  # "one" | "plus" (p+) | "star" (p*)
    target_class_uris: tuple[str, ...] = ()


# ── Column sources ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PropertySource:
    """A datatype value at the end of ``path`` (empty path = a property on the root)."""

    predicate: str
    path: tuple[Hop, ...] = ()
    collapse: str | None = None  # for a to-many path: first|concat|count|min|max
    kind: str = "property"


@dataclass(frozen=True)
class NodeSource:
    """The entity reached by ``path``, shown as its label or uri (a relation column)."""

    path: tuple[Hop, ...]
    show: str = "label"  # "label" | "uri"
    collapse: str | None = None
    kind: str = "node"


@dataclass(frozen=True)
class AggregateSource:
    """A measure: an aggregate over the set of nodes/values reached by ``path``."""

    fn: str  # count | countDistinct | sum | avg | min | max
    path: tuple[Hop, ...] = ()
    of_kind: str | None = None  # "node" | "property" | None (None ⇒ count reached nodes)
    of_predicate: str | None = None
    kind: str = "aggregate"


ColumnSource = PropertySource | NodeSource | AggregateSource


@dataclass(frozen=True)
class Column:
    id: str  # ^[A-Za-z0-9_]+$ — interpolated as the SPARQL var ?col_<id>
    datatype: str  # string | number | date | boolean | iri
    source: ColumnSource
    label: str = ""
    visible: bool = True


# ── Anchors (what a row is) ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ClassAnchor:
    class_uris: tuple[str, ...]
    kind: str = "class"


@dataclass(frozen=True)
class InstancesAnchor:
    instance_uris: tuple[str, ...]
    kind: str = "instances"


RootAnchor = ClassAnchor | InstancesAnchor


# ── Filter tree (AND/OR/NOT + leaf conditions) ────────────────────────────────


@dataclass(frozen=True)
class FilterColumnTarget:
    column_id: str
    kind: str = "column"


@dataclass(frozen=True)
class FilterSourceTarget:
    """An inline branch (follow-to-constrain) → compiles to EXISTS."""

    source: ColumnSource
    kind: str = "source"


FilterTarget = FilterColumnTarget | FilterSourceTarget


@dataclass(frozen=True)
class FilterCondition:
    target: FilterTarget
    operator: str
    value: Any = None  # scalar | (lo, hi) | tuple[...] — shape per operator
    op: str = "cond"


@dataclass(frozen=True)
class FilterGroup:
    op: str  # "and" | "or"
    children: tuple[FilterNode, ...] = ()


@dataclass(frozen=True)
class FilterNot:
    child: FilterNode
    op: str = "not"


FilterNode = FilterCondition | FilterGroup | FilterNot


@dataclass(frozen=True)
class SortKey:
    column_id: str
    direction: str = "asc"  # "asc" | "desc"


# ── List mode spec ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ListSpec:
    graph_uris: tuple[str, ...]
    root: RootAnchor
    columns: tuple[Column, ...]
    filters: FilterNode | None = None
    sort: tuple[SortKey, ...] = ()
    mode: str = "list"
    version: int = 1


# ── Aggregate mode spec (modelled now; compiler support lands in a later step) ──


@dataclass(frozen=True)
class Dimension:
    id: str
    show_kind: str  # "property" | "node-label" | "node-uri"
    path: tuple[Hop, ...] = ()
    show_predicate: str | None = None
    label: str = ""


@dataclass(frozen=True)
class Measure:
    id: str
    fn: str
    path: tuple[Hop, ...] = ()
    of_kind: str | None = None
    of_predicate: str | None = None
    label: str = ""


@dataclass(frozen=True)
class AggregateSpec:
    graph_uris: tuple[str, ...]
    fact: RootAnchor
    group_by: tuple[Dimension, ...]
    measures: tuple[Measure, ...]
    filters: FilterNode | None = None
    sort: tuple[SortKey, ...] = ()
    mode: str = "aggregate"
    version: int = 1


ViewQuerySpec = ListSpec | AggregateSpec


# ── Compiler in/out ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompileContext:
    """Capability flags + ontology hints the compiler needs but does not fetch itself."""

    fts_backend: str = "none"  # "jena_text" | "none" (CONTAINS fallback)
    fts_predicate: str = "http://jena.apache.org/text#query"
    # Predicates known to be single-valued per row (owl:FunctionalProperty / SHACL maxCount 1).
    # Drives the requiredness rule: a positively-filtered single-valued column → required join.
    single_valued_predicates: frozenset[str] = frozenset()
    max_hops: int = 8
    max_columns: int = 64
    page_limit: int = 100


@dataclass(frozen=True)
class ColumnMeta:
    id: str
    label: str
    datatype: str
    role: str  # "dimension" | "node" | "measure"


@dataclass(frozen=True)
class Page:
    """Per-request pagination. Never persisted in the spec (AUDIT §7b.0).

    ``after`` is the decoded keyset cursor: the previous page's last row's sort values
    followed by its ``?root`` IRI (so ``len(after) == len(sort) + 1``). When keyset is not
    eligible the service uses ``offset`` instead.
    """

    limit: int = 100
    offset: int = 0
    after: tuple[Any, ...] | None = None


@dataclass(frozen=True)
class CompiledQuery:
    sparql: str  # the page query
    count_sparql: str  # COUNT(DISTINCT ?root) — spec minus sort/page/projection-only
    columns: tuple[ColumnMeta, ...]
    var_for_column: dict[str, str] = field(default_factory=dict)
    # True ⇒ this page used OFFSET (keyset not eligible: nullable/measure/collapse sort key).
    uses_offset_fallback: bool = False
    # Column ids in ORDER BY order (sort keys then implicit ?root) — the service builds the
    # next_cursor by reading these vars off the last returned row.
    order_columns: tuple[str, ...] = ()


# ── Response DTOs (service output; the primary adapter maps these to Pydantic) ──


@dataclass(frozen=True)
class CellData:
    value: Any  # scalar coerced per the column datatype (str | number | bool | None)
    uri: str | None = None  # set for node cells → entity click-through


@dataclass(frozen=True)
class PageInfoData:
    limit: int
    has_more: bool
    next_cursor: str | None = None
    offset_fallback: bool = False


@dataclass(frozen=True)
class CountInfoData:
    total: int
    computed_at: str
    status: str  # "exact" | "cached" | "stale" | "estimate"
    cache_key: str


@dataclass(frozen=True)
class QueryResultData:
    mode: str  # "list" | "aggregate"
    columns: tuple[ColumnMeta, ...]
    rows: tuple[dict[str, CellData], ...]
    page: PageInfoData
    count: CountInfoData
    resolved_sparql: str | None = None
    # The grain individual IRI for each row (the ``?root`` binding), aligned with ``rows``;
    # ``None`` where there is no root (aggregate mode). Lets the UI inspect/open a row's entity.
    row_uris: tuple[str | None, ...] = ()


# ── Column discovery (GET /api/graph/columns) ──────────────────────────────────


@dataclass(frozen=True)
class FacetBucketData:
    value: str
    count: int


@dataclass(frozen=True)
class FacetResultData:
    column_id: str
    faceted: bool  # False ⇒ refused (measure / unfacetable); see `reason`
    buckets: tuple[FacetBucketData, ...] = ()
    distinct_count: int = 0
    truncated: bool = False
    reason: str = ""


@dataclass(frozen=True)
class TargetClassData:
    uri: str
    label: str
    instance_count: int


@dataclass(frozen=True)
class DiscoveredColumn:
    id: str  # stable slug (predicate + direction) — referenced by a spec column
    predicate_uri: str
    label: str
    kind: str  # "property" | "relation"
    direction: str  # "out" (class is subject) | "in" (class is object)
    datatype: str  # string | number | date | boolean | iri
    datatype_source: str  # "ontology-range" | "sampled" | "default"
    source: str  # "ontology" | "data" | "both"
    instance_count: int  # distinct anchor instances that use this predicate (0 ⇒ ontology-only)
    is_functional: bool  # to-one ⇒ no collapse needed (drives compiler single_valued hint)
    facetable: bool
    target_classes: tuple[TargetClassData, ...] = ()


# ── Entity search (GET /api/graph/search) ───────────────────────────────────────


@dataclass(frozen=True)
class SearchHitData:
    """One free-text search hit — a class or an individual, tagged with its ``kind`` so the
    frontend can configure the Composer grain from a click."""

    uri: str  # the class or individual IRI
    label: str  # display label (rdfs:label or URI fragment)
    kind: str  # "class" | "individual"
    class_uri: str  # individual: its rdf:type domain class; class: == uri
    class_label: str  # label of class_uri
    graph_uri: str  # a data graph that contains this hit
    instance_count: int  # class hit: # instances of the class in that graph; individual hit: 0
