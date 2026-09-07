"""Pydantic transport for POST /api/graph/query (AUDIT §7b.1, §7b.2).

Mirrors the frozen-dataclass domain spec in ``query/query__schema.py`` (snake_case, house
style — no aliases). ``to_domain()`` converts request models → domain dataclasses at the
adapter boundary so the service/compiler stay Pydantic-free; ``from_result()`` maps the
domain ``QueryResultData`` back to the response model.
"""

from __future__ import annotations

from typing import Annotated, Literal

from naas_abi.apps.nexus.apps.api.app.services.graph.query import query__schema as d
from pydantic import BaseModel, Field

_Operator = Literal[
    "eq", "neq", "contains", "notContains", "startsWith", "endsWith",
    "lt", "lte", "gt", "gte", "between",
    "in", "notIn", "isEmpty", "isNotEmpty",
    "is", "isNot", "hasRelation",
]
_Datatype = Literal["string", "number", "date", "boolean", "iri"]
_Collapse = Literal["first", "concat", "count", "min", "max"]
_AggFn = Literal["count", "countDistinct", "sum", "avg", "min", "max"]


class HopModel(BaseModel):
    predicate: str = Field(min_length=1)
    direction: Literal["out", "in"] = "out"
    quantifier: Literal["one", "plus", "star"] = "one"
    target_class_uris: list[str] = Field(default_factory=list)

    def to_domain(self) -> d.Hop:
        return d.Hop(self.predicate, self.direction, self.quantifier, tuple(self.target_class_uris))


def _path(path: list[HopModel]) -> tuple[d.Hop, ...]:
    return tuple(h.to_domain() for h in path)


class PropertySourceModel(BaseModel):
    kind: Literal["property"] = "property"
    predicate: str = Field(min_length=1)
    path: list[HopModel] = Field(default_factory=list)
    collapse: _Collapse | None = None

    def to_domain(self) -> d.PropertySource:
        return d.PropertySource(self.predicate, _path(self.path), self.collapse)


class NodeSourceModel(BaseModel):
    kind: Literal["node"] = "node"
    path: list[HopModel] = Field(min_length=1)
    show: Literal["label", "uri"] = "label"
    collapse: _Collapse | None = None

    def to_domain(self) -> d.NodeSource:
        return d.NodeSource(_path(self.path), self.show, self.collapse)


class AggregateSourceModel(BaseModel):
    kind: Literal["aggregate"] = "aggregate"
    fn: _AggFn
    path: list[HopModel] = Field(default_factory=list)
    of_kind: Literal["node", "property"] | None = None
    of_predicate: str | None = None

    def to_domain(self) -> d.AggregateSource:
        return d.AggregateSource(self.fn, _path(self.path), self.of_kind, self.of_predicate)


ColumnSourceModel = Annotated[
    PropertySourceModel | NodeSourceModel | AggregateSourceModel, Field(discriminator="kind")
]


class ColumnModel(BaseModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_]+$")
    datatype: _Datatype
    source: ColumnSourceModel
    label: str = ""
    visible: bool = True

    def to_domain(self) -> d.Column:
        return d.Column(self.id, self.datatype, self.source.to_domain(), self.label, self.visible)


class ClassAnchorModel(BaseModel):
    kind: Literal["class"] = "class"
    class_uris: list[str] = Field(min_length=1)

    def to_domain(self) -> d.ClassAnchor:
        return d.ClassAnchor(tuple(self.class_uris))


class InstancesAnchorModel(BaseModel):
    kind: Literal["instances"] = "instances"
    instance_uris: list[str] = Field(min_length=1)

    def to_domain(self) -> d.InstancesAnchor:
        return d.InstancesAnchor(tuple(self.instance_uris))


RootAnchorModel = Annotated[ClassAnchorModel | InstancesAnchorModel, Field(discriminator="kind")]


class FilterColumnTargetModel(BaseModel):
    kind: Literal["column"] = "column"
    column_id: str = Field(min_length=1)

    def to_domain(self) -> d.FilterColumnTarget:
        return d.FilterColumnTarget(self.column_id)


class FilterSourceTargetModel(BaseModel):
    kind: Literal["source"] = "source"
    source: ColumnSourceModel

    def to_domain(self) -> d.FilterSourceTarget:
        return d.FilterSourceTarget(self.source.to_domain())


FilterTargetModel = Annotated[
    FilterColumnTargetModel | FilterSourceTargetModel, Field(discriminator="kind")
]

_Scalar = str | int | float | bool


class FilterConditionModel(BaseModel):
    op: Literal["cond"] = "cond"
    target: FilterTargetModel
    operator: _Operator
    value: _Scalar | list[_Scalar] | None = None

    def to_domain(self) -> d.FilterCondition:
        value = tuple(self.value) if isinstance(self.value, list) else self.value
        return d.FilterCondition(self.target.to_domain(), self.operator, value)


class FilterGroupModel(BaseModel):
    op: Literal["and", "or"]
    children: list[FilterNodeModel] = Field(min_length=1, max_length=100)

    def to_domain(self) -> d.FilterGroup:
        return d.FilterGroup(self.op, tuple(c.to_domain() for c in self.children))


class FilterNotModel(BaseModel):
    op: Literal["not"] = "not"
    child: FilterNodeModel

    def to_domain(self) -> d.FilterNot:
        return d.FilterNot(self.child.to_domain())


FilterNodeModel = Annotated[
    FilterConditionModel | FilterGroupModel | FilterNotModel, Field(discriminator="op")
]

# Resolve the recursive forward refs now that FilterNodeModel exists.
FilterGroupModel.model_rebuild()
FilterNotModel.model_rebuild()


class SortKeyModel(BaseModel):
    column_id: str = Field(min_length=1)
    direction: Literal["asc", "desc"] = "asc"

    def to_domain(self) -> d.SortKey:
        return d.SortKey(self.column_id, self.direction)


class ListSpecModel(BaseModel):
    mode: Literal["list"] = "list"
    version: Literal[1] = 1
    graph_uris: list[str] = Field(min_length=1)
    root: RootAnchorModel
    columns: list[ColumnModel] = Field(min_length=1)
    filters: FilterNodeModel | None = None
    sort: list[SortKeyModel] = Field(default_factory=list)

    def to_domain(self) -> d.ListSpec:
        return d.ListSpec(
            tuple(self.graph_uris),
            self.root.to_domain(),
            tuple(c.to_domain() for c in self.columns),
            self.filters.to_domain() if self.filters is not None else None,
            tuple(s.to_domain() for s in self.sort),
        )


class DimensionModel(BaseModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_]+$")
    show_kind: Literal["property", "node-label", "node-uri"]
    path: list[HopModel] = Field(default_factory=list)
    show_predicate: str | None = None
    label: str = ""

    def to_domain(self) -> d.Dimension:
        return d.Dimension(self.id, self.show_kind, _path(self.path), self.show_predicate, self.label)


class MeasureModel(BaseModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_]+$")
    fn: _AggFn
    path: list[HopModel] = Field(default_factory=list)
    of_kind: Literal["node", "property"] | None = None
    of_predicate: str | None = None
    label: str = ""

    def to_domain(self) -> d.Measure:
        return d.Measure(self.id, self.fn, _path(self.path), self.of_kind, self.of_predicate, self.label)


class AggregateSpecModel(BaseModel):
    mode: Literal["aggregate"] = "aggregate"
    version: Literal[1] = 1
    graph_uris: list[str] = Field(min_length=1)
    fact: RootAnchorModel
    group_by: list[DimensionModel] = Field(min_length=1)
    measures: list[MeasureModel] = Field(min_length=1)
    filters: FilterNodeModel | None = None
    sort: list[SortKeyModel] = Field(default_factory=list)

    def to_domain(self) -> d.AggregateSpec:
        return d.AggregateSpec(
            tuple(self.graph_uris),
            self.fact.to_domain(),
            tuple(g.to_domain() for g in self.group_by),
            tuple(m.to_domain() for m in self.measures),
            self.filters.to_domain() if self.filters is not None else None,
            tuple(s.to_domain() for s in self.sort),
        )


ViewQuerySpecModel = Annotated[ListSpecModel | AggregateSpecModel, Field(discriminator="mode")]


class GraphQueryRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    spec: ViewQuerySpecModel
    cursor: str | None = None
    limit: int | None = Field(default=None, ge=1, le=5000)
    include_sparql: bool = False
    force_count_refresh: bool = False
    # "Always refresh" tick in the Composer: bypass the result cache and re-run the SPARQL.
    force_refresh: bool = False


# ── Response ──────────────────────────────────────────────────────────────────


class CellModel(BaseModel):
    value: str | float | int | bool | None = None
    uri: str | None = None


class ColumnMetaModel(BaseModel):
    id: str
    label: str
    datatype: str
    role: str


class PageInfoModel(BaseModel):
    limit: int
    has_more: bool
    next_cursor: str | None = None
    offset_fallback: bool = False


class CountInfoModel(BaseModel):
    total: int
    computed_at: str
    status: str
    cache_key: str


class GraphQueryResponse(BaseModel):
    mode: str
    columns: list[ColumnMetaModel]
    rows: list[dict[str, CellModel]]
    page: PageInfoModel
    count: CountInfoModel
    resolved_sparql: str | None = None
    # Grain individual IRI per row (aligned with ``rows``); ``None`` in aggregate mode.
    row_uris: list[str | None] = []

    @classmethod
    def from_result(cls, r: d.QueryResultData) -> GraphQueryResponse:
        return cls(
            mode=r.mode,
            columns=[ColumnMetaModel(id=c.id, label=c.label, datatype=c.datatype, role=c.role) for c in r.columns],
            rows=[{cid: CellModel(value=cell.value, uri=cell.uri) for cid, cell in row.items()} for row in r.rows],
            page=PageInfoModel(
                limit=r.page.limit, has_more=r.page.has_more,
                next_cursor=r.page.next_cursor, offset_fallback=r.page.offset_fallback,
            ),
            count=CountInfoModel(
                total=r.count.total, computed_at=r.count.computed_at,
                status=r.count.status, cache_key=r.count.cache_key,
            ),
            resolved_sparql=r.resolved_sparql,
            row_uris=list(r.row_uris),
        )


# ── POST /api/graph/query/facets ────────────────────────────────────────────────


class GraphFacetsRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    spec: ListSpecModel
    target_column_id: str = Field(min_length=1)
    search: str = Field(default="", max_length=200)
    limit: int = Field(default=50, ge=1, le=200)


class FacetBucketModel(BaseModel):
    value: str
    count: int


class GraphFacetsResponse(BaseModel):
    column_id: str
    faceted: bool
    buckets: list[FacetBucketModel] = []
    distinct_count: int = 0
    truncated: bool = False
    reason: str = ""

    @classmethod
    def from_domain(cls, r: d.FacetResultData) -> GraphFacetsResponse:
        return cls(
            column_id=r.column_id, faceted=r.faceted,
            buckets=[FacetBucketModel(value=b.value, count=b.count) for b in r.buckets],
            distinct_count=r.distinct_count, truncated=r.truncated, reason=r.reason,
        )


# ── GET /api/graph/columns response ─────────────────────────────────────────────


class TargetClassModel(BaseModel):
    uri: str
    label: str
    instance_count: int
    graph: str = ""  # a named graph the target class's instances live in


class DiscoveredColumnModel(BaseModel):
    id: str
    predicate_uri: str
    label: str
    kind: str
    direction: str
    datatype: str
    datatype_source: str
    source: str
    instance_count: int
    is_functional: bool
    facetable: bool
    target_classes: list[TargetClassModel] = []


class GraphColumnsResponse(BaseModel):
    class_uris: list[str]
    columns: list[DiscoveredColumnModel]

    @classmethod
    def from_domain(cls, class_uris: list[str], cols: tuple) -> GraphColumnsResponse:
        return cls(
            class_uris=class_uris,
            columns=[
                DiscoveredColumnModel(
                    id=c.id, predicate_uri=c.predicate_uri, label=c.label, kind=c.kind,
                    direction=c.direction, datatype=c.datatype, datatype_source=c.datatype_source,
                    source=c.source, instance_count=c.instance_count, is_functional=c.is_functional,
                    facetable=c.facetable,
                    target_classes=[
                        TargetClassModel(uri=t.uri, label=t.label, instance_count=t.instance_count, graph=t.graph)
                        for t in c.target_classes
                    ],
                )
                for c in cols
            ],
        )


# ── GET /api/graph/search response ──────────────────────────────────────────────


class SearchHitModel(BaseModel):
    uri: str
    label: str
    kind: str
    class_uri: str
    class_label: str
    graph_uri: str
    instance_count: int


class GraphSearchResponse(BaseModel):
    query: str
    results: list[SearchHitModel]

    @classmethod
    def from_domain(cls, query: str, hits: tuple) -> GraphSearchResponse:
        return cls(
            query=query,
            results=[
                SearchHitModel(
                    uri=h.uri, label=h.label, kind=h.kind, class_uri=h.class_uri,
                    class_label=h.class_label, graph_uri=h.graph_uri, instance_count=h.instance_count,
                )
                for h in hits
            ],
        )
