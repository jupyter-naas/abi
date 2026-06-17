// Building the FilterNode boolean tree from the Excel-style per-column filter UI.
//
// Each column can carry (a) a set of values ticked in the facet dropdown and/or (b) a
// free-form condition (operator + value). Both lower to `cond` nodes targeting the
// column; a column with both is the AND of the two; the whole table filter is the AND of
// every column's node. AUDIT.md §7a "Filter semantics".

import { LIST_OPERATORS, NULLARY_OPERATORS, RANGE_OPERATORS } from './columns'
import type {
  ColumnSource,
  Datatype,
  FilterCondition,
  FilterNode,
  FilterTarget,
  FilterValue,
  Operator,
  Scalar,
} from './types'

/** One free-form condition (operator + value) on a column. */
export interface ColumnCondition {
  operator: Operator
  value: FilterValue
}

/** Per-column filter state held by the table UI. */
export interface ColumnFilterState {
  /** Values ticked in the facet dropdown (literals, or URIs for iri columns). */
  selected?: string[]
  /** Free-form conditions, combined by `combinator`. */
  conditions?: ColumnCondition[]
  /** How `conditions` combine: 'and' (match all) or 'or' (match any). Defaults to 'and'. */
  combinator?: 'and' | 'or'
  /** @deprecated legacy single-condition operator — still read when `conditions` is absent. */
  operator?: Operator
  /** @deprecated legacy single-condition value. */
  value?: FilterValue
}

/** The effective condition list: `conditions` if present, else the legacy single condition. */
export function conditionsOf(state: ColumnFilterState | undefined): ColumnCondition[] {
  if (!state) return []
  if (state.conditions && state.conditions.length > 0) return state.conditions
  if (state.operator) return [{ operator: state.operator, value: state.value ?? null }]
  return []
}

export function isBlank(state: ColumnFilterState | undefined): boolean {
  if (!state) return true
  const hasSelected = !!state.selected && state.selected.length > 0
  return !hasSelected && conditionsOf(state).length === 0
}

/** Coerce a raw scalar (often a string from an <input>) to the column's datatype. */
export function coerceScalar(raw: Scalar, datatype: Datatype): Scalar {
  if (datatype === 'number') {
    const n = typeof raw === 'number' ? raw : Number(String(raw).trim())
    return Number.isFinite(n) ? n : (raw as Scalar)
  }
  if (datatype === 'boolean') {
    if (typeof raw === 'boolean') return raw
    const s = String(raw).trim().toLowerCase()
    if (s === 'true') return true
    if (s === 'false') return false
    return raw
  }
  // string / date / iri stay as-is (date is an ISO string).
  return raw
}

function columnTarget(columnId: string): FilterTarget {
  return { kind: 'column', column_id: columnId }
}
function sourceTarget(source: ColumnSource): FilterTarget {
  return { kind: 'source', source }
}
function conditionFor(target: FilterTarget, operator: Operator, value: FilterValue): FilterCondition {
  return { op: 'cond', target, operator, value }
}
function condition(columnId: string, operator: Operator, value: FilterValue): FilterCondition {
  return conditionFor(columnTarget(columnId), operator, value)
}

/** True when (operator, value) is well-formed enough to send. */
export function isValidCondition(operator: Operator, value: FilterValue): boolean {
  if (NULLARY_OPERATORS.has(operator)) return true
  if (RANGE_OPERATORS.has(operator)) {
    return Array.isArray(value) && value.length === 2 && value.every((v) => v !== '' && v != null)
  }
  if (LIST_OPERATORS.has(operator)) {
    return Array.isArray(value) && value.length > 0
  }
  return value !== '' && value !== null && value !== undefined && !Array.isArray(value)
}

/** Coerce a free-form condition value to the datatype, dropping it for nullary operators. */
function coerceConditionValue(datatype: Datatype, operator: Operator, value: FilterValue): FilterValue {
  if (NULLARY_OPERATORS.has(operator)) return null
  if (Array.isArray(value)) return value.map((v) => coerceScalar(v, datatype))
  if (value != null) return coerceScalar(value, datatype)
  return value
}

/** Lower a free-form condition against any target, or null when incomplete/invalid. */
function targetConditionToNode(
  target: FilterTarget,
  datatype: Datatype,
  operator: Operator,
  value: FilterValue,
): FilterCondition | null {
  const coerced = coerceConditionValue(datatype, operator, value)
  if (!isValidCondition(operator, coerced)) return null
  return conditionFor(target, operator, coerced)
}

/** Lower one filter state (facet selection + free-form condition) against any target. */
export function targetFilterToNode(
  target: FilterTarget,
  datatype: Datatype,
  state: ColumnFilterState | undefined,
): FilterNode | null {
  if (isBlank(state) || !state) return null
  const nodes: FilterNode[] = []
  if (state.selected && state.selected.length > 0) {
    nodes.push(conditionFor(target, 'in', [...state.selected]))
  }
  const condNodes = conditionsOf(state)
    .map((c) => targetConditionToNode(target, datatype, c.operator, c.value))
    .filter((n): n is FilterCondition => n != null)
  if (condNodes.length === 1) {
    nodes.push(condNodes[0])
  } else if (condNodes.length > 1) {
    // Multiple conditions on one column combine by the chosen combinator (default AND).
    nodes.push({ op: state.combinator === 'or' ? 'or' : 'and', children: condNodes })
  }
  if (nodes.length === 0) return null
  if (nodes.length === 1) return nodes[0]
  return { op: 'and', children: nodes }
}

/**
 * Lower one column's free-form condition to a node, coercing the value to the datatype.
 * Returns null when the condition is incomplete/invalid.
 */
export function conditionToNode(
  columnId: string,
  datatype: Datatype,
  operator: Operator,
  value: FilterValue,
): FilterCondition | null {
  return targetConditionToNode(columnTarget(columnId), datatype, operator, value)
}

/** Lower a facet multi-select to an `in` condition (URIs for iri columns, literals else). */
export function selectionToNode(columnId: string, selected: string[]): FilterCondition | null {
  if (!selected || selected.length === 0) return null
  return condition(columnId, 'in', [...selected])
}

/** Lower one column's full filter state to a node (AND of selection + condition). */
export function columnFilterToNode(
  columnId: string,
  datatype: Datatype,
  state: ColumnFilterState | undefined,
): FilterNode | null {
  return targetFilterToNode(columnTarget(columnId), datatype, state)
}

/** Lower one filter state against an inline source path (branch / inverse-path conditions). */
export function sourceFilterToNode(
  source: ColumnSource,
  datatype: Datatype,
  state: ColumnFilterState | undefined,
): FilterNode | null {
  return targetFilterToNode(sourceTarget(source), datatype, state)
}

/** AND together a list of nodes; null/empty drop out. Returns null when nothing remains. */
export function andAll(nodes: Array<FilterNode | null>): FilterNode | null {
  const kept = nodes.filter((n): n is FilterNode => n != null)
  if (kept.length === 0) return null
  if (kept.length === 1) return kept[0]
  return { op: 'and', children: kept }
}

/**
 * Combine every column's filter state into one AND tree. `datatypes` maps column id →
 * datatype (needed for value coercion). Columns absent from the map default to 'string'.
 */
export function buildFilterTree(
  filters: Record<string, ColumnFilterState>,
  datatypes: Record<string, Datatype>,
): FilterNode | null {
  const nodes = Object.entries(filters).map(([columnId, state]) =>
    columnFilterToNode(columnId, datatypes[columnId] ?? 'string', state),
  )
  return andAll(nodes)
}
