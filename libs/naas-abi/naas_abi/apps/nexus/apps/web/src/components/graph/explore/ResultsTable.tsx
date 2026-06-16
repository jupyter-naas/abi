'use client'

import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Filter, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters'
import type { ExploreAction, ExploreState } from '@/lib/graph-query/explore-state'
import type { Datatype, FacetBucket, GraphQueryResponse } from '@/lib/graph-query/types'
import { ColumnFilterPopover } from './ColumnFilterPopover'
import { formatCell } from './format'

export interface ResultsTableProps {
  result: GraphQueryResponse
  state: ExploreState
  dispatch: (action: ExploreAction) => void
  running: boolean
  rowsLoadingMore: boolean
  facetableById: Record<string, boolean>
  loadFacets: (columnId: string, search: string) => Promise<FacetBucket[]>
  onLoadMore: () => void
}

export function ResultsTable({
  result,
  state,
  dispatch,
  running,
  rowsLoadingMore,
  facetableById,
  loadFacets,
  onLoadMore,
}: ResultsTableProps) {
  const [openFilter, setOpenFilter] = useState<{ id: string; left: number; top: number } | null>(null)
  const sort = state.sort[0]

  // The popover is portalled with fixed coords, so close it if the page/table scrolls
  // (it would otherwise detach from its column).
  useEffect(() => {
    if (!openFilter) return
    const close = () => setOpenFilter(null)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [openFilter])

  const setFilter = (columnId: string, next: ColumnFilterState) =>
    dispatch({ type: 'setFilter', columnId, state: next })

  return (
    <div className="flex h-full flex-col" data-testid="explore-results">
      <div className="relative flex-1 overflow-auto">
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 z-10 bg-background">
            <tr>
              {result.columns.map((col) => {
                const sorted = sort?.column_id === col.id
                const dir = sorted ? sort.direction : null
                const filterState = state.filters[col.id]
                const active = !isBlank(filterState)
                return (
                  <th
                    key={col.id}
                    className="relative whitespace-nowrap border-b border-r px-3 py-1.5 text-left font-medium"
                  >
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => dispatch({ type: 'toggleSort', columnId: col.id })}
                        className="flex items-center gap-1 hover:text-workspace-accent"
                        data-testid={`column-sort-${col.id}`}
                        title="Sort"
                      >
                        <span>{col.label || col.id}</span>
                        {dir === 'asc' && <ChevronUp size={12} />}
                        {dir === 'desc' && <ChevronDown size={12} />}
                      </button>
                      <button
                        onClick={(e) => {
                          if (openFilter?.id === col.id) {
                            setOpenFilter(null)
                            return
                          }
                          const r = e.currentTarget.getBoundingClientRect()
                          setOpenFilter({ id: col.id, left: r.left, top: r.bottom + 4 })
                        }}
                        className={cn(
                          'rounded p-0.5 hover:bg-muted-foreground/20',
                          active && 'text-workspace-accent',
                        )}
                        data-testid={`column-filter-${col.id}`}
                        data-filter-trigger=""
                        title="Filter"
                      >
                        <Filter size={11} />
                      </button>
                    </div>
                    {openFilter?.id === col.id && (
                      <ColumnFilterPopover
                        columnId={col.id}
                        label={col.label || col.id}
                        datatype={(col.datatype as Datatype) ?? 'string'}
                        facetable={facetableById[col.id] ?? false}
                        anchor={{ left: openFilter.left, top: openFilter.top }}
                        state={filterState}
                        onChange={(next) => setFilter(col.id, next)}
                        onClear={() => dispatch({ type: 'clearFilter', columnId: col.id })}
                        loadFacets={loadFacets}
                        onClose={() => setOpenFilter(null)}
                      />
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, i) => (
              <tr key={i} className="hover:bg-muted/40" data-testid="explore-row">
                {result.columns.map((col) => {
                  const cell = formatCell(row[col.id])
                  return (
                    <td
                      key={col.id}
                      className="max-w-xs truncate border-b border-r px-3 py-1"
                      title={cell.uri ?? cell.text}
                    >
                      {cell.isEmpty ? (
                        <span className="text-muted-foreground/50">—</span>
                      ) : cell.uri ? (
                        <span className="font-mono text-[11px] text-workspace-accent">{cell.text}</span>
                      ) : (
                        cell.text
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
            {result.rows.length === 0 && !running && (
              <tr>
                <td
                  colSpan={Math.max(1, result.columns.length)}
                  className="px-3 py-8 text-center text-muted-foreground"
                  data-testid="explore-empty"
                >
                  No rows match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {running && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60">
            <Loader2 className="animate-spin text-muted-foreground" />
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t px-3 py-1.5 text-xs text-muted-foreground">
        <span data-testid="explore-count">
          {result.rows.length} of {result.count.total.toLocaleString()} rows
          {result.count.status && result.count.status !== 'exact' ? ` (${result.count.status})` : ''}
        </span>
        <div className="flex items-center gap-2">
          {result.page.offset_fallback && <span title="Sorted page uses offset paging">offset paging</span>}
          {result.page.has_more && (
            <button
              onClick={onLoadMore}
              disabled={rowsLoadingMore}
              data-testid="explore-load-more"
              className="flex items-center gap-1 rounded border px-2 py-0.5 hover:bg-muted disabled:opacity-50"
            >
              {rowsLoadingMore && <Loader2 size={12} className="animate-spin" />}
              Load more
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
