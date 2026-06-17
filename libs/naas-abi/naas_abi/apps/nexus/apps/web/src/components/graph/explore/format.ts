// Pure cell/URI formatting helpers for the Explore results table.

import type { Cell } from '@/lib/graph-query/types'

/** Last path/hash segment of an IRI, for compact display. */
export function compactUri(uri: string): string {
  if (!uri) return ''
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop()
      if (tail) return tail
    }
  }
  return uri
}

export interface CellDisplay {
  text: string
  /** The full IRI when the cell is an entity reference, else null. */
  uri: string | null
  isEmpty: boolean
}

/** Resolve a cell to its display text: prefer a label, fall back to a compacted IRI. */
export function formatCell(cell: Cell | undefined): CellDisplay {
  if (!cell || (cell.value == null && !cell.uri)) {
    return { text: '', uri: null, isEmpty: true }
  }
  if (cell.uri) {
    const label =
      cell.value != null && String(cell.value).length > 0 ? String(cell.value) : compactUri(cell.uri)
    return { text: label, uri: cell.uri, isEmpty: false }
  }
  if (typeof cell.value === 'boolean') {
    return { text: cell.value ? 'true' : 'false', uri: null, isEmpty: false }
  }
  return { text: String(cell.value), uri: null, isEmpty: cell.value === '' }
}
