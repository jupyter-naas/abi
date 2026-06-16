// Mapping discovered columns (GET /api/graph/columns) → spec Columns, plus the
// per-datatype operator vocabulary that drives the Excel-style filter dropdowns.

import type { Column, ColumnSource, Datatype, DiscoveredColumn, Hop, Operator } from './types'

/** Operators offered for each datatype in the column filter UI (order = display order). */
export const OPERATORS_BY_DATATYPE: Record<Datatype, Operator[]> = {
  string: ['contains', 'notContains', 'eq', 'neq', 'startsWith', 'endsWith', 'in', 'notIn', 'isEmpty', 'isNotEmpty'],
  number: ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'between', 'isEmpty', 'isNotEmpty'],
  date: ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'between', 'isEmpty', 'isNotEmpty'],
  boolean: ['eq', 'neq', 'isEmpty', 'isNotEmpty'],
  iri: ['is', 'isNot', 'in', 'notIn', 'hasRelation', 'isEmpty', 'isNotEmpty'],
}

export const OPERATOR_LABELS: Record<Operator, string> = {
  eq: 'equals',
  neq: 'not equals',
  contains: 'contains',
  notContains: 'does not contain',
  startsWith: 'starts with',
  endsWith: 'ends with',
  lt: 'less than',
  lte: 'at most',
  gt: 'greater than',
  gte: 'at least',
  between: 'between',
  in: 'is any of',
  notIn: 'is none of',
  isEmpty: 'is empty',
  isNotEmpty: 'is not empty',
  is: 'is',
  isNot: 'is not',
  hasRelation: 'has relation',
}

/** Operators that take no value (presence checks). */
export const NULLARY_OPERATORS: ReadonlySet<Operator> = new Set<Operator>(['isEmpty', 'isNotEmpty'])
/** Operators whose value is a list. */
export const LIST_OPERATORS: ReadonlySet<Operator> = new Set<Operator>(['in', 'notIn'])
/** Operators whose value is a [lo, hi] pair. */
export const RANGE_OPERATORS: ReadonlySet<Operator> = new Set<Operator>(['between'])

export function operatorsFor(datatype: Datatype): Operator[] {
  return OPERATORS_BY_DATATYPE[datatype] ?? OPERATORS_BY_DATATYPE.string
}

export function defaultOperator(datatype: Datatype): Operator {
  return operatorsFor(datatype)[0]
}

/**
 * Sanitize a discovered-column id into the spec's `^[A-Za-z0-9_]+$` shape. The backend
 * already slugs predicate fragments, but ad-hoc/odd predicates can still produce stray
 * characters; we keep ids stable and collision-resistant by suffixing when needed.
 */
export function sanitizeColumnId(raw: string): string {
  const cleaned = raw.replace(/[^A-Za-z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '')
  return cleaned.length > 0 ? cleaned.slice(0, 128) : 'col'
}

/** Build the column `source` for a discovered predicate (direct, zero-hop). */
export function sourceForDiscovered(dc: DiscoveredColumn): ColumnSource {
  if (dc.kind === 'relation') {
    return {
      kind: 'node',
      path: [{ predicate: dc.predicate_uri, direction: dc.direction, quantifier: 'one' }],
      show: 'label',
    }
  }
  return { kind: 'property', predicate: dc.predicate_uri, path: [] }
}

/** Map a discovered column → a spec Column. Relations carry datatype 'iri'. */
export function discoveredToColumn(dc: DiscoveredColumn): Column {
  const datatype: Datatype = dc.kind === 'relation' ? 'iri' : dc.datatype
  return {
    id: sanitizeColumnId(dc.id),
    datatype,
    source: sourceForDiscovered(dc),
    label: dc.label,
    visible: true,
  }
}

/**
 * Build a 2-hop column that reads a `field` on the target of a `relation`
 * (e.g. extracted_by › model_name). This is how off-spine conditions are added: the
 * resulting column is filterable like any other.
 */
export function expandedColumn(relation: DiscoveredColumn, field: DiscoveredColumn): Column {
  const hop = { predicate: relation.predicate_uri, direction: relation.direction, quantifier: 'one' as const }
  const id = sanitizeColumnId(`${relation.id}__${field.id}`)
  const label = `${relation.label} › ${field.label}`
  if (field.kind === 'relation') {
    return {
      id,
      datatype: 'iri',
      source: {
        kind: 'node',
        path: [hop, { predicate: field.predicate_uri, direction: field.direction, quantifier: 'one' }],
        show: 'label',
      },
      label,
      visible: true,
    }
  }
  return {
    id,
    datatype: field.datatype,
    source: { kind: 'property', predicate: field.predicate_uri, path: [hop] },
    label,
    visible: true,
  }
}

/**
 * Build a column for a field discovered on a DIFFERENT (e.g. earlier-grain) class, reached
 * via `prefix` hops from the current grain. Used to add columns from an ancestor level after
 * a drill. `labelPrefix` (the source class) namespaces the id/label so it can't collide.
 */
export function columnThroughPath(dc: DiscoveredColumn, prefix: Hop[], labelPrefix: string): Column {
  const base = discoveredToColumn(dc)
  const source: ColumnSource =
    base.source.kind === 'node'
      ? { ...base.source, path: [...prefix, ...base.source.path] }
      : base.source.kind === 'property'
        ? { ...base.source, path: [...prefix, ...(base.source.path ?? [])] }
        : base.source
  return {
    ...base,
    id: sanitizeColumnId(`${labelPrefix}_${base.id}`),
    label: `${labelPrefix} · ${dc.label}`,
    source,
  }
}

/**
 * Map a set of discovered columns → spec Columns, guaranteeing unique ids (later
 * duplicates get a numeric suffix). Order is preserved.
 */
export function discoveredToColumns(discovered: DiscoveredColumn[]): Column[] {
  const seen = new Map<string, number>()
  const out: Column[] = []
  for (const dc of discovered) {
    const col = discoveredToColumn(dc)
    const n = seen.get(col.id) ?? 0
    seen.set(col.id, n + 1)
    if (n > 0) col.id = sanitizeColumnId(`${col.id}_${n}`)
    out.push(col)
  }
  return out
}
