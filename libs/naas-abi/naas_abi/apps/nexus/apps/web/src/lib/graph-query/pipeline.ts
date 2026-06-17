// The navigation spine: drilling "follow a relation" changes the grain (what one row is).
//
// A spine is an ordered list of nodes [root, …, grain]. Each non-root node records the
// hop (`via`) used to reach it. The grain is the last node; its class anchors the query.
// Filters applied at an *ancestor* level are kept on that node and, at lowering time,
// re-expressed as constraints on the grain via the INVERSE path (reverse the hops, flip
// each direction). AUDIT.md §7a "Authoring model: a navigation pipeline".

import { sourceFilterToNode, type ColumnFilterState } from './filters'
import type { Column, ColumnSource, Datatype, Direction, FilterNode, Hop } from './types'

export interface SpineHop {
  predicate: string
  direction: Direction
  label?: string
}

export interface SpineNode {
  classUri: string
  classLabel: string
  /** How this node was reached from the previous one (undefined for the root). */
  via?: SpineHop
  /** Constraints frozen at this level (only set on ancestors after drilling past them). */
  filters: Record<string, ColumnFilterState>
  /** Column defs at this level, needed to resolve a frozen filter's column → its source. */
  columns: Column[]
}

export function rootNode(classUri: string, classLabel: string): SpineNode {
  return { classUri, classLabel, filters: {}, columns: [] }
}

/** The grain node (terminal) of a spine, or undefined for an empty spine. */
export function grainNode(spine: SpineNode[]): SpineNode | undefined {
  return spine.length > 0 ? spine[spine.length - 1] : undefined
}

export function grainClassUris(spine: SpineNode[]): string[] {
  const grain = grainNode(spine)
  return grain ? [grain.classUri] : []
}

function flip(direction: Direction): Direction {
  return direction === 'out' ? 'in' : 'out'
}

/** The single inverse hop for a follow step (used to re-project carried columns one level up). */
export function flipHop(via: SpineHop): Hop {
  return { predicate: via.predicate, direction: flip(via.direction), quantifier: 'one' }
}

/**
 * Re-project a column from the level being left onto the new grain by prefixing its path
 * with the inverse hop, so it still resolves from a grain row. Columns that were the level's
 * own attributes (empty path) get their label prefixed with the level's class for clarity.
 */
export function rebaseColumn(col: Column, hop: Hop, leavingLabel: string): Column {
  const existing = col.source.kind === 'node' ? col.source.path : (col.source.path ?? [])
  const wasOwn = existing.length === 0
  const label = wasOwn && leavingLabel ? `${leavingLabel} · ${col.label || col.id}` : col.label || col.id
  const source: ColumnSource =
    col.source.kind === 'node'
      ? { ...col.source, path: [hop, ...col.source.path] }
      : { ...col.source, path: [hop, ...(col.source.path ?? [])] }
  return { ...col, label, source }
}

/**
 * Path of hops FROM the grain (terminal) back TO the ancestor at `ancestorIndex`.
 * Built by reversing the hops between the ancestor and the grain and flipping each
 * direction, so a downward drill `paper -has_chunks-> chunk -has_extracted_item-> item`
 * inverts to `item -[has_extracted_item,in]-> chunk -[has_chunks,in]-> paper`.
 */
export function inversePathToAncestor(spine: SpineNode[], ancestorIndex: number): Hop[] {
  const hops: Hop[] = []
  for (let i = spine.length - 1; i > ancestorIndex; i--) {
    const via = spine[i].via
    if (!via) continue
    hops.push({ predicate: via.predicate, direction: flip(via.direction), quantifier: 'one' })
  }
  return hops
}

/** Prefix a column's own source with the inverse path so it reads from `ancestor` entities. */
function rebaseSource(source: ColumnSource, prefix: Hop[]): { source: ColumnSource; datatype: Datatype } | null {
  if (source.kind === 'property') {
    return {
      source: { kind: 'property', predicate: source.predicate, path: [...prefix, ...(source.path ?? [])] },
      datatype: 'string',
    }
  }
  if (source.kind === 'node') {
    return { source: { kind: 'node', path: [...prefix, ...source.path], show: source.show ?? 'label' }, datatype: 'iri' }
  }
  return null // aggregate sources are not used as ancestor filter targets
}

function datatypeOfColumn(col: Column): Datatype {
  return col.datatype
}

/**
 * Lower every ancestor node's frozen filters to grain-level constraints (via inverse
 * paths). Returns the list of FilterNodes to AND with the grain's own filters.
 */
export function upstreamConditions(spine: SpineNode[]): FilterNode[] {
  const out: FilterNode[] = []
  for (let i = 0; i < spine.length - 1; i++) {
    const node = spine[i]
    const entries = Object.entries(node.filters)
    if (entries.length === 0) continue
    const prefix = inversePathToAncestor(spine, i)
    const byId = new Map(node.columns.map((c) => [c.id, c]))
    for (const [colId, state] of entries) {
      const col = byId.get(colId)
      if (!col) continue
      const rebased = rebaseSource(col.source, prefix)
      if (!rebased) continue
      const datatype = col.source.kind === 'property' ? datatypeOfColumn(col) : 'iri'
      const cond = sourceFilterToNode(rebased.source, datatype, state)
      if (cond) out.push(cond)
    }
  }
  return out
}

/** Human-readable breadcrumb labels for the spine. */
export function breadcrumb(spine: SpineNode[]): { classLabel: string; viaLabel?: string }[] {
  return spine.map((n) => ({ classLabel: n.classLabel, viaLabel: n.via?.label ?? n.via?.predicate }))
}
