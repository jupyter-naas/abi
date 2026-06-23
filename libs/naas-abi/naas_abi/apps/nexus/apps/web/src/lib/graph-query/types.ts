// Transport + spec types for the Explore query API.
//
// These mirror the backend Pydantic transport one-for-one (snake_case, no aliases —
// see apps/api/.../graph/query/adapters/primary/graph_query__primary_adapter__schemas.py).
// The JSON on the wire uses snake_case keys, so we keep them snake_case here too and
// never rename at the boundary. The canonical design lives in AUDIT.md §7a / §7b.

// ── Vocabularies ────────────────────────────────────────────────────────────────

export type Datatype = 'string' | 'number' | 'date' | 'boolean' | 'iri'

export type Operator =
  | 'eq' | 'neq' | 'contains' | 'notContains' | 'startsWith' | 'endsWith'
  | 'lt' | 'lte' | 'gt' | 'gte' | 'between'
  | 'in' | 'notIn' | 'isEmpty' | 'isNotEmpty'
  | 'is' | 'isNot' | 'hasRelation'

export type Collapse = 'first' | 'concat' | 'count' | 'min' | 'max'
export type AggFn = 'count' | 'countDistinct' | 'sum' | 'avg' | 'min' | 'max'
export type Direction = 'out' | 'in'
export type Quantifier = 'one' | 'plus' | 'star'

export type Scalar = string | number | boolean
export type FilterValue = Scalar | Scalar[] | null

// ── Path / hops ─────────────────────────────────────────────────────────────────

export interface Hop {
  predicate: string
  direction?: Direction // default 'out'
  quantifier?: Quantifier // default 'one'
  target_class_uris?: string[]
}
export type Path = Hop[] // [] = the root itself

// ── Column sources ──────────────────────────────────────────────────────────────

export interface PropertySource {
  kind: 'property'
  predicate: string
  path?: Hop[]
  collapse?: Collapse | null
}
export interface NodeSource {
  kind: 'node'
  path: Hop[] // min 1 hop
  show?: 'label' | 'uri'
  collapse?: Collapse | null
}
export interface AggregateSource {
  kind: 'aggregate'
  fn: AggFn
  path?: Hop[]
  of_kind?: 'node' | 'property' | null
  of_predicate?: string | null
}
export type ColumnSource = PropertySource | NodeSource | AggregateSource

export interface Column {
  id: string // ^[A-Za-z0-9_]+$, referenced by filters/sort
  datatype: Datatype
  source: ColumnSource
  label?: string
  visible?: boolean
}

// ── Anchors ─────────────────────────────────────────────────────────────────────

export interface ClassAnchor {
  kind: 'class'
  class_uris: string[]
}
export interface InstancesAnchor {
  kind: 'instances'
  instance_uris: string[]
}
export type RootAnchor = ClassAnchor | InstancesAnchor

// ── Filter tree ─────────────────────────────────────────────────────────────────

export type FilterTarget = { kind: 'column'; column_id: string } | { kind: 'source'; source: ColumnSource }

export interface FilterCondition {
  op: 'cond'
  target: FilterTarget
  operator: Operator
  value?: FilterValue
}
export interface FilterGroup {
  op: 'and' | 'or'
  children: FilterNode[]
}
export interface FilterNot {
  op: 'not'
  child: FilterNode
}
export type FilterNode = FilterCondition | FilterGroup | FilterNot

export interface SortKey {
  column_id: string
  direction?: 'asc' | 'desc'
}

// ── Specs ───────────────────────────────────────────────────────────────────────

export interface ListSpec {
  mode: 'list'
  version: 1
  graph_uris: string[]
  root: RootAnchor
  columns: Column[]
  filters?: FilterNode | null
  sort?: SortKey[]
}

export interface Dimension {
  id: string
  show_kind: 'property' | 'node-label' | 'node-uri'
  path?: Hop[]
  show_predicate?: string | null
  label?: string
}
export interface Measure {
  id: string
  fn: AggFn
  path?: Hop[]
  of_kind?: 'node' | 'property' | null
  of_predicate?: string | null
  label?: string
}
export interface AggregateSpec {
  mode: 'aggregate'
  version: 1
  graph_uris: string[]
  fact: RootAnchor
  group_by: Dimension[]
  measures: Measure[]
  filters?: FilterNode | null
  sort?: SortKey[]
}

export type ViewQuerySpec = ListSpec | AggregateSpec

// ── Request / response: POST /api/graph/query ───────────────────────────────────

export interface GraphQueryRequest {
  workspace_id: string
  spec: ViewQuerySpec
  cursor?: string | null
  limit?: number | null
  include_sparql?: boolean
  force_count_refresh?: boolean
}

export interface Cell {
  value: string | number | boolean | null
  uri?: string | null
}
export type Row = Record<string, Cell>

export interface ColumnMeta {
  id: string
  label: string
  datatype: string
  role: string
}
export interface PageInfo {
  limit: number
  has_more: boolean
  next_cursor?: string | null
  offset_fallback?: boolean
}
export interface CountInfo {
  total: number
  computed_at: string
  status: string
  cache_key: string
}
export interface GraphQueryResponse {
  mode: string
  columns: ColumnMeta[]
  rows: Row[]
  page: PageInfo
  count: CountInfo
  resolved_sparql?: string | null
  /** Grain individual IRI per row (aligned with `rows`); null in aggregate mode. */
  row_uris?: (string | null)[]
}

// ── Request / response: POST /api/graph/query/facets ────────────────────────────

export interface GraphFacetsRequest {
  workspace_id: string
  spec: ListSpec
  target_column_id: string
  search?: string
  limit?: number
}
export interface FacetBucket {
  value: string
  count: number
}
export interface GraphFacetsResponse {
  column_id: string
  faceted: boolean
  buckets: FacetBucket[]
  distinct_count: number
  truncated: boolean
  reason: string
}

// ── Response: GET /api/graph/columns ────────────────────────────────────────────

export interface TargetClass {
  uri: string
  label: string
  instance_count: number
  /** A named graph the target class lives in — used to scope a follow to exactly that graph. */
  graph?: string
}
export interface DiscoveredColumn {
  id: string
  predicate_uri: string
  label: string
  kind: 'property' | 'relation'
  direction: Direction
  datatype: Datatype
  datatype_source: string
  source: 'ontology' | 'data' | 'both'
  instance_count: number
  is_functional: boolean
  facetable: boolean
  target_classes: TargetClass[]
}
export interface GraphColumnsResponse {
  class_uris: string[]
  columns: DiscoveredColumn[]
}
