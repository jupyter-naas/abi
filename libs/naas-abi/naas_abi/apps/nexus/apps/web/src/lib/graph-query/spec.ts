// Assemble a ViewQuerySpec from the Explore UI draft, plus light client-side validation
// that mirrors the backend guards (QueryGuards) so we can disable "Run" with a helpful
// message instead of round-tripping to a 400.

import { buildFilterTree, type ColumnFilterState } from './filters'
import type {
  AggregateSpec,
  Column,
  Datatype,
  Dimension,
  ListSpec,
  Measure,
  RootAnchor,
  SortKey,
} from './types'

// Mirrors backend QueryGuards (apps/api/.../graph/query/guards.py).
export const GUARDS = {
  MAX_COLUMNS: 60,
  MAX_GRAPHS: 25,
  MAX_PATH_HOPS: 8,
  MAX_PAGE_LIMIT: 5000,
  DEFAULT_PAGE_LIMIT: 100,
} as const

export interface ListDraft {
  graphUris: string[]
  /** Class anchor — one row per instance of these classes. */
  classUris: string[]
  /** Fixed-instance anchor (takes precedence over classUris when non-empty). */
  instanceUris?: string[]
  columns: Column[]
  filters: Record<string, ColumnFilterState>
  sort: SortKey[]
}

function datatypeMap(columns: Column[]): Record<string, Datatype> {
  const m: Record<string, Datatype> = {}
  for (const c of columns) m[c.id] = c.datatype
  return m
}

export function anchorFor(classUris: string[], instanceUris?: string[]): RootAnchor {
  if (instanceUris && instanceUris.length > 0) {
    return { kind: 'instances', instance_uris: [...instanceUris] }
  }
  return { kind: 'class', class_uris: [...classUris] }
}

export function buildListSpec(draft: ListDraft): ListSpec {
  const filters = buildFilterTree(draft.filters, datatypeMap(draft.columns))
  return {
    mode: 'list',
    version: 1,
    graph_uris: [...draft.graphUris],
    root: anchorFor(draft.classUris, draft.instanceUris),
    columns: draft.columns.map((c) => ({ ...c })),
    filters,
    sort: [...draft.sort],
  }
}

export interface AggregateDraft {
  graphUris: string[]
  classUris: string[]
  instanceUris?: string[]
  groupBy: Dimension[]
  measures: Measure[]
  /** Filters keyed by group-by / measure column id (uses the same per-column UI state). */
  filters: Record<string, ColumnFilterState>
  filterDatatypes: Record<string, Datatype>
  sort: SortKey[]
}

export function buildAggregateSpec(draft: AggregateDraft): AggregateSpec {
  const filters = buildFilterTree(draft.filters, draft.filterDatatypes)
  return {
    mode: 'aggregate',
    version: 1,
    graph_uris: [...draft.graphUris],
    fact: anchorFor(draft.classUris, draft.instanceUris),
    group_by: draft.groupBy.map((d) => ({ ...d })),
    measures: draft.measures.map((m) => ({ ...m })),
    filters,
    sort: [...draft.sort],
  }
}

// ── Validation ──────────────────────────────────────────────────────────────────

function anchorErrors(root: RootAnchor, errors: string[]): void {
  if (root.kind === 'class' && root.class_uris.length === 0) {
    errors.push('Pick at least one class to anchor the rows.')
  }
  if (root.kind === 'instances' && root.instance_uris.length === 0) {
    errors.push('Pick at least one instance.')
  }
}

/** Returns a list of human-readable problems; empty list = ready to run. */
export function listSpecErrors(spec: ListSpec): string[] {
  const errors: string[] = []
  if (spec.graph_uris.length === 0) errors.push('Select at least one graph.')
  if (spec.graph_uris.length > GUARDS.MAX_GRAPHS) errors.push(`Too many graphs (max ${GUARDS.MAX_GRAPHS}).`)
  anchorErrors(spec.root, errors)
  if (spec.columns.length === 0) errors.push('Add at least one column.')
  if (spec.columns.length > GUARDS.MAX_COLUMNS) errors.push(`Too many columns (max ${GUARDS.MAX_COLUMNS}).`)
  const ids = new Set<string>()
  for (const c of spec.columns) {
    if (ids.has(c.id)) errors.push(`Duplicate column id "${c.id}".`)
    ids.add(c.id)
  }
  for (const s of spec.sort ?? []) {
    if (!ids.has(s.column_id)) errors.push(`Sort references unknown column "${s.column_id}".`)
  }
  return errors
}

export function aggregateSpecErrors(spec: AggregateSpec): string[] {
  const errors: string[] = []
  if (spec.graph_uris.length === 0) errors.push('Select at least one graph.')
  anchorErrors(spec.fact, errors)
  if (spec.group_by.length === 0) errors.push('Add at least one group-by dimension.')
  if (spec.measures.length === 0) errors.push('Add at least one measure.')
  return errors
}

export function isRunnable(spec: ListSpec | AggregateSpec): boolean {
  return (spec.mode === 'list' ? listSpecErrors(spec) : aggregateSpecErrors(spec)).length === 0
}
