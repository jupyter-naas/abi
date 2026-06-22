// Pure reducer for the Explore builder. Holds the draft the UI manipulates (graphs,
// anchor, columns, per-column filters, sort, mode) and lowers it to a ViewQuerySpec via
// the spec builders. Kept framework-free so it unit-tests without React.

import { andAll, type ColumnFilterState } from './filters'
import { flipHop, rebaseColumn, rootNode, upstreamConditions, type SpineHop, type SpineNode } from './pipeline'
import { buildAggregateSpec, buildListSpec } from './spec'
import type {
  Collapse,
  Column,
  Datatype,
  Dimension,
  FilterNode,
  ListSpec,
  Measure,
  RootAnchor,
  SortKey,
  ViewQuerySpec,
} from './types'

export type ExploreMode = 'list' | 'aggregate'

/**
 * Max navigation depth. Each follow rebases carried columns with one more inverse hop, so
 * depth is bounded to keep those paths within the backend's MAX_PATH_HOPS (8) guard — and
 * to stop cyclic relations (A → B → A → …) from drilling forever.
 */
export const MAX_DRILL_DEPTH = 6

export interface ExploreState {
  graphUris: string[]
  /** Authoritative grain anchor; kept = grainClassUris(spine) whenever the spine is set. */
  classUris: string[]
  instanceUris: string[]
  mode: ExploreMode
  /** Navigation spine [root, …, grain]. Empty until a class is chosen. */
  spine: SpineNode[]
  columns: Column[]
  filters: Record<string, ColumnFilterState>
  sort: SortKey[]
  // aggregate mode
  groupBy: Dimension[]
  measures: Measure[]
}

export function initialExploreState(): ExploreState {
  return {
    graphUris: [],
    classUris: [],
    instanceUris: [],
    mode: 'list',
    spine: [],
    columns: [],
    filters: {},
    sort: [],
    groupBy: [],
    measures: [],
  }
}

export type ExploreAction =
  | { type: 'setGraphs'; graphUris: string[] }
  | { type: 'toggleGraph'; graphUri: string }
  | { type: 'setClasses'; classUris: string[] }
  | { type: 'setRoot'; classUri: string; classLabel: string }
  | { type: 'setGrain'; graphUris: string[]; classUri: string; classLabel: string; instanceUris?: string[] }
  | { type: 'follow'; via: SpineHop; targetClassUri: string; targetClassLabel: string; graphUris?: string[] }
  | { type: 'drillTo'; index: number }
  | { type: 'setInstances'; instanceUris: string[] }
  | { type: 'setMode'; mode: ExploreMode }
  | { type: 'setColumns'; columns: Column[] }
  | { type: 'addColumn'; column: Column; graphUris?: string[] }
  | { type: 'removeColumn'; columnId: string }
  | { type: 'moveColumn'; columnId: string; delta: number }
  | { type: 'reorderColumn'; columnId: string; toIndex: number }
  | { type: 'setColumnCollapse'; columnId: string; collapse: Collapse | null }
  | { type: 'setFilter'; columnId: string; state: ColumnFilterState }
  | { type: 'clearFilter'; columnId: string }
  | { type: 'clearAllFilters' }
  | { type: 'toggleSort'; columnId: string }
  | { type: 'setGroupBy'; groupBy: Dimension[] }
  | { type: 'setMeasures'; measures: Measure[] }
  | { type: 'load'; state: ExploreState }
  | { type: 'reset' }

function withoutFilter(filters: Record<string, ColumnFilterState>, columnId: string): Record<string, ColumnFilterState> {
  const next = { ...filters }
  delete next[columnId]
  return next
}

function moveItem<T>(items: T[], index: number, delta: number): T[] {
  const target = index + delta
  if (index < 0 || target < 0 || target >= items.length) return items
  const next = [...items]
  const [item] = next.splice(index, 1)
  next.splice(target, 0, item)
  return next
}

export function exploreReducer(state: ExploreState, action: ExploreAction): ExploreState {
  switch (action.type) {
    case 'setGraphs':
      // Changing graphs invalidates the whole anchor — classes (and their filters/columns)
      // belong to the graph, so reset the spine, grain, columns, filters and sort.
      return {
        ...state,
        graphUris: action.graphUris,
        classUris: [],
        instanceUris: [],
        spine: [],
        columns: [],
        filters: {},
        sort: [],
        groupBy: [],
        measures: [],
      }
    case 'toggleGraph': {
      // Multi-graph (cross-graph views): add/remove one graph WITHOUT resetting the grain.
      // Columns are predicate-based, so a graph that lacks a predicate just yields null cells;
      // re-discovery (keyed on graphUris) refreshes the available class/column list.
      const has = state.graphUris.includes(action.graphUri)
      const graphUris = has
        ? state.graphUris.filter((g) => g !== action.graphUri)
        : [...state.graphUris, action.graphUri]
      return { ...state, graphUris }
    }
    case 'setClasses': {
      const spine = action.classUris[0] ? [rootNode(action.classUris[0], '')] : []
      return { ...state, classUris: action.classUris, spine, columns: [], filters: {}, sort: [], groupBy: [], measures: [] }
    }
    case 'setRoot':
      return {
        ...state,
        classUris: [action.classUri],
        instanceUris: [],
        spine: [rootNode(action.classUri, action.classLabel)],
        columns: [],
        filters: {},
        sort: [],
        groupBy: [],
        measures: [],
      }
    case 'setGrain':
      // External (search) grain configuration: anchor a fresh query on a class in the given
      // graph(s), optionally pinned to specific instances. Resets columns/filters like setRoot;
      // the auto-seed effect then fills in the new grain's default columns.
      return {
        ...initialExploreState(),
        graphUris: action.graphUris,
        classUris: [action.classUri],
        instanceUris: action.instanceUris ?? [],
        spine: [rootNode(action.classUri, action.classLabel)],
      }
    case 'follow': {
      if (state.spine.length === 0 || state.spine.length >= MAX_DRILL_DEPTH) return state
      // Freeze the current grain's filters + columns onto the terminal node, then push.
      const last = state.spine.length - 1
      const leavingLabel = state.spine[last].classLabel
      const frozen = state.spine.map((n, i) =>
        i === last ? { ...n, filters: state.filters, columns: state.columns } : n,
      )
      const next: SpineNode = {
        classUri: action.targetClassUri,
        classLabel: action.targetClassLabel,
        via: action.via,
        filters: {},
        columns: [],
      }
      // Re-project the columns picked at this level onto the new grain via the inverse hop,
      // so they keep showing on the drilled-into rows.
      const hop = flipHop(action.via)
      const carried = state.columns.map((c) => rebaseColumn(c, hop, leavingLabel))
      // The followed class often lives in a DIFFERENT named graph than the current grain
      // (cross-graph relations). Add exactly that graph (from the relation's target metadata)
      // to the scope so the new grain's rows + columns resolve — without over-widening to every
      // graph. A single-graph scope would otherwise return an empty grain.
      const graphUris = action.graphUris?.length
        ? [...new Set([...state.graphUris, ...action.graphUris])]
        : state.graphUris
      return {
        ...state,
        graphUris,
        spine: [...frozen, next],
        classUris: [action.targetClassUri],
        instanceUris: [],
        columns: carried,
        filters: {},
        sort: [],
      }
    }
    case 'drillTo': {
      const last = state.spine.length - 1
      if (action.index < 0 || action.index >= state.spine.length || action.index === last) return state
      const target = state.spine[action.index]
      // Truncate to the target and unfreeze it back into live filters/columns.
      const spine = state.spine
        .slice(0, action.index + 1)
        .map((n, i) => (i === action.index ? { ...n, filters: {}, columns: [] } : n))
      return {
        ...state,
        spine,
        classUris: [target.classUri],
        columns: target.columns,
        filters: target.filters,
        sort: [],
      }
    }
    case 'setInstances':
      return { ...state, instanceUris: action.instanceUris }
    case 'setMode':
      return { ...state, mode: action.mode }
    case 'setColumns':
      return { ...state, columns: action.columns }
    case 'addColumn': {
      if (state.columns.some((c) => c.id === action.column.id)) return state
      // A column reached through a cross-graph relation lives in another named graph; add that
      // graph to the query scope (FROM-union) so the column resolves instead of rendering blank.
      // Scope only ever GROWS here (and on follow) — never auto-shrunk on removeColumn, since
      // another column/filter may still rely on the graph. The graph picker is the manual control
      // to narrow scope back.
      const graphUris = action.graphUris?.length
        ? [...new Set([...state.graphUris, ...action.graphUris])]
        : state.graphUris
      return { ...state, graphUris, columns: [...state.columns, action.column] }
    }
    case 'removeColumn':
      return {
        ...state,
        columns: state.columns.filter((c) => c.id !== action.columnId),
        filters: withoutFilter(state.filters, action.columnId),
        sort: state.sort.filter((s) => s.column_id !== action.columnId),
      }
    case 'moveColumn': {
      const index = state.columns.findIndex((c) => c.id === action.columnId)
      if (index === -1) return state
      return { ...state, columns: moveItem(state.columns, index, action.delta) }
    }
    case 'reorderColumn': {
      // Drag-and-drop reorder. `toIndex` is expressed in post-removal coordinates (the index
      // the column should land at once it has been lifted out of its current slot).
      const from = state.columns.findIndex((c) => c.id === action.columnId)
      if (from === -1) return state
      const next = [...state.columns]
      const [item] = next.splice(from, 1)
      const to = Math.max(0, Math.min(action.toIndex, next.length))
      next.splice(to, 0, item)
      return { ...state, columns: next }
    }
    case 'setColumnCollapse':
      return {
        ...state,
        columns: state.columns.map((c) =>
          c.id !== action.columnId || c.source.kind === 'aggregate'
            ? c
            : { ...c, source: { ...c.source, collapse: action.collapse ?? undefined } },
        ),
      }
    case 'setFilter':
      return { ...state, filters: { ...state.filters, [action.columnId]: action.state } }
    case 'clearFilter':
      return { ...state, filters: withoutFilter(state.filters, action.columnId) }
    case 'clearAllFilters':
      return { ...state, filters: {} }
    case 'toggleSort': {
      const current = state.sort[0]
      if (!current || current.column_id !== action.columnId) {
        return { ...state, sort: [{ column_id: action.columnId, direction: 'asc' }] }
      }
      if (current.direction === 'asc') {
        return { ...state, sort: [{ column_id: action.columnId, direction: 'desc' }] }
      }
      return { ...state, sort: [] } // third click clears the sort
    }
    case 'setGroupBy':
      return { ...state, groupBy: action.groupBy }
    case 'setMeasures':
      return { ...state, measures: action.measures }
    case 'load':
      return action.state
    case 'reset':
      return initialExploreState()
    default:
      return state
  }
}

/** Map of column id → datatype, used for aggregate-mode filter coercion. */
function aggregateFilterDatatypes(state: ExploreState): Record<string, Datatype> {
  const m: Record<string, Datatype> = {}
  for (const d of state.groupBy) m[d.id] = d.show_kind === 'property' ? 'string' : 'iri'
  for (const measure of state.measures) m[measure.id] = 'number'
  return m
}

/** Lower the current draft to a ViewQuerySpec. */
export function specFromState(state: ExploreState): ViewQuerySpec {
  const instanceUris = state.instanceUris.length > 0 ? state.instanceUris : undefined
  if (state.mode === 'aggregate') {
    return buildAggregateSpec({
      graphUris: state.graphUris,
      classUris: state.classUris,
      instanceUris,
      groupBy: state.groupBy,
      measures: state.measures,
      filters: state.filters,
      filterDatatypes: aggregateFilterDatatypes(state),
      sort: state.sort,
    })
  }
  const listSpec: ListSpec = buildListSpec({
    graphUris: state.graphUris,
    classUris: state.classUris,
    instanceUris,
    columns: state.columns,
    filters: state.filters,
    sort: state.sort,
  })
  // Fold every ancestor level's frozen filters in as grain-level constraints.
  const upstream = upstreamConditions(state.spine)
  if (upstream.length === 0) return listSpec
  return { ...listSpec, filters: andAll([listSpec.filters ?? null, ...upstream]) }
}

// ── Loading a saved view back into the builder ──────────────────────────────────

/**
 * Best-effort inverse of the builder's filter lowering: walk a FilterNode and accumulate each
 * column's facet selection + free-form conditions (and their AND/OR combinator) into the
 * per-column map. Only shapes the builder emits are decoded; a cross-column OR, a `not`, or a
 * source-target condition is ignored (the per-column UI can't represent it).
 */
export function filtersFromNode(node: FilterNode | null | undefined): Record<string, ColumnFilterState> {
  const acc: Record<string, ColumnFilterState> = {}
  const ensure = (id: string): ColumnFilterState => {
    if (!acc[id]) acc[id] = {}
    return acc[id]
  }
  const pushCond = (id: string, cond: Extract<FilterNode, { op: 'cond' }>) => {
    if (cond.operator === 'in' && Array.isArray(cond.value)) {
      ensure(id).selected = cond.value.map((v) => String(v))
      return
    }
    const s = ensure(id)
    if (!s.conditions) s.conditions = []
    s.conditions.push({ operator: cond.operator, value: cond.value ?? null })
  }
  const walk = (n: FilterNode) => {
    if (n.op === 'cond') {
      if (n.target.kind === 'column') pushCond(n.target.column_id, n)
      return
    }
    if (n.op === 'and') {
      n.children.forEach(walk)
      return
    }
    if (n.op === 'or') {
      // Representable only as one column's OR-conditions: every child a column cond, same column.
      const colConds = n.children.filter(
        (c): c is Extract<FilterNode, { op: 'cond' }> => c.op === 'cond' && c.target.kind === 'column',
      )
      const ids = new Set(
        colConds.map((c) => (c.target as { kind: 'column'; column_id: string }).column_id),
      )
      if (colConds.length === n.children.length && ids.size === 1) {
        const id = [...ids][0]
        ensure(id).combinator = 'or'
        for (const c of colConds) pushCond(id, c)
      }
      return
    }
    // 'not' — unsupported in the per-column builder.
  }
  if (node) walk(node)
  return acc
}

function classOf(anchor: RootAnchor): string[] {
  return anchor.kind === 'class' ? [...anchor.class_uris] : []
}
function instancesOf(anchor: RootAnchor): string[] {
  return anchor.kind === 'instances' ? [...anchor.instance_uris] : []
}

/** Reconstruct an ExploreState from a persisted ViewQuerySpec (for loading saved views). */
export function stateFromSpec(spec: ViewQuerySpec): ExploreState {
  const base = initialExploreState()
  const filters = filtersFromNode(spec.filters)
  const sort: SortKey[] = [...(spec.sort ?? [])]
  if (spec.mode === 'aggregate') {
    return {
      ...base,
      mode: 'aggregate',
      graphUris: [...spec.graph_uris],
      classUris: classOf(spec.fact),
      instanceUris: instancesOf(spec.fact),
      groupBy: spec.group_by.map((d) => ({ ...d })),
      measures: spec.measures.map((m) => ({ ...m })),
      filters,
      sort,
    }
  }
  const grain = classOf(spec.root)
  // A loaded view starts flat (single-node spine); drill history isn't persisted in v1.
  const spine: SpineNode[] = grain[0] ? [{ ...rootNode(grain[0], ''), columns: spec.columns.map((c) => ({ ...c })) }] : []
  return {
    ...base,
    mode: 'list',
    graphUris: [...spec.graph_uris],
    classUris: grain,
    instanceUris: instancesOf(spec.root),
    spine,
    columns: spec.columns.map((c) => ({ ...c })),
    filters,
    sort,
  }
}
