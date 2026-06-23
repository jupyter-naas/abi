// CSV serialization + download for the Explore results table.

import type { ColumnMeta, Row } from '@/lib/graph-query/types'
import { formatCell } from './format'

/** Escape one field per RFC 4180: quote it when it contains a delimiter, quote or newline. */
function escapeCsvField(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
}

/**
 * Serialize the result table to CSV text — one header row, then one row per result row.
 * Cell text mirrors what the table shows (a label for entity cells, the formatted literal
 * otherwise); missing/empty cells become empty fields.
 */
export function rowsToCsv(columns: Pick<ColumnMeta, 'id' | 'label'>[], rows: Row[]): string {
  const header = columns.map((c) => escapeCsvField(c.label || c.id)).join(',')
  const body = rows.map((row) => columns.map((c) => escapeCsvField(formatCell(row[c.id]).text)).join(','))
  return [header, ...body].join('\r\n')
}

/** Trigger a browser download of CSV text (UTF-8 with a BOM so Excel detects the encoding). */
export function downloadCsv(filename: string, csv: string): void {
  const bom = String.fromCharCode(0xfeff)
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
