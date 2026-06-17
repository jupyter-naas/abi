'use client'

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, ChevronUp, ExternalLink, Filter, GripVertical, Loader2, PanelRight } from 'lucide-react'
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
  /** Open the inline inspect drawer for an individual IRI (cell click / row menu). */
  onInspect?: (uri: string) => void
  /** Navigate to the full Individuals view for an individual IRI (row menu). */
  onOpenIndividual?: (uri: string) => void
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
  onInspect,
  onOpenIndividual,
}: ResultsTableProps) {
  const [openFilter, setOpenFilter] = useState<{ id: string; left: number; top: number } | null>(null)
  const [menu, setMenu] = useState<{ x: number; y: number; uri: string } | null>(null)
  // Drag-to-reorder column header state.
  const [dragCol, setDragCol] = useState<string | null>(null)
  const [dragOverCol, setDragOverCol] = useState<string | null>(null)
  const [dragInsertAfter, setDragInsertAfter] = useState(false)
  const sort = state.sort[0]

  const onColumnDrop = (targetId: string, insertAfter: boolean) => {
    setDragOverCol(null)
    const dragged = dragCol
    setDragCol(null)
    if (!dragged || dragged === targetId) return
    const cols = result.columns
    const from = cols.findIndex((c) => c.id === dragged)
    let to = cols.findIndex((c) => c.id === targetId)
    if (from === -1 || to === -1) return
    if (from < to) to-- // index in post-removal coordinates
    dispatch({ type: 'reorderColumn', columnId: dragged, toIndex: insertAfter ? to + 1 : to })
  }

  // Close the right-click row menu on any click / scroll / resize.
  useEffect(() => {
    if (!menu) return
    const close = () => setMenu(null)
    window.addEventListener('click', close)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [menu])

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
          <thead className="sticky top-0 z-20 bg-card">
            <tr className="bg-workspace-accent-10 text-muted-foreground">
              {result.columns.map((col) => {
                const sorted = sort?.column_id === col.id
                const dir = sorted ? sort.direction : null
                const filterState = state.filters[col.id]
                const active = !isBlank(filterState)
                const isDragging = dragCol === col.id
                const isDropTarget = dragOverCol === col.id && dragCol !== col.id
                return (
                  <th
                    key={col.id}
                    draggable
                    onDragStart={(e) => {
                      setDragCol(col.id)
                      e.dataTransfer.effectAllowed = 'move'
                    }}
                    onDragOver={(e) => {
                      e.preventDefault()
                      e.dataTransfer.dropEffect = 'move'
                      if (col.id === dragCol) return
                      const rect = e.currentTarget.getBoundingClientRect()
                      setDragOverCol(col.id)
                      setDragInsertAfter(e.clientX > rect.left + rect.width / 2)
                    }}
                    onDragLeave={(e) => {
                      if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOverCol(null)
                    }}
                    onDrop={(e) => {
                      e.preventDefault()
                      const rect = e.currentTarget.getBoundingClientRect()
                      onColumnDrop(col.id, e.clientX > rect.left + rect.width / 2)
                    }}
                    onDragEnd={() => {
                      setDragCol(null)
                      setDragOverCol(null)
                    }}
                    className={cn(
                      'relative cursor-grab select-none whitespace-nowrap border-b border-r p-0 text-left align-middle',
                      isDragging && 'opacity-40',
                      isDropTarget && !dragInsertAfter && 'border-l-[3px] border-l-workspace-accent',
                      isDropTarget && dragInsertAfter && 'border-r-[3px] border-r-workspace-accent',
                    )}
                  >
                    <div className="flex items-stretch">
                      <button
                        onClick={() => dispatch({ type: 'toggleSort', columnId: col.id })}
                        className={cn(
                          'flex flex-1 items-center gap-1 px-2 py-2 text-left font-semibold uppercase tracking-wide transition-colors hover:bg-workspace-accent-10',
                          sorted && 'text-foreground',
                        )}
                        data-testid={`column-sort-${col.id}`}
                        title="Sort (drag the header to reorder)"
                      >
                        <GripVertical size={11} className="shrink-0 text-muted-foreground/40" />
                        <span className="truncate">{col.label || col.id}</span>
                        {dir === 'asc' && <ChevronUp size={12} className="shrink-0" />}
                        {dir === 'desc' && <ChevronDown size={12} className="shrink-0" />}
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
                          'flex shrink-0 items-center border-l border-border px-1.5 py-2 transition-colors hover:bg-workspace-accent-10',
                          active ? 'bg-workspace-accent-10 text-workspace-accent' : 'text-muted-foreground hover:text-foreground',
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
            {result.rows.map((row, i) => {
              const rowUri = result.row_uris?.[i] ?? null
              return (
                <tr
                  key={i}
                  className="hover:bg-muted/40"
                  data-testid="explore-row"
                  onDoubleClick={() => {
                    if (!rowUri || !onInspect) return
                    window.getSelection()?.removeAllRanges() // drop the accidental text selection
                    onInspect(rowUri)
                  }}
                  onContextMenu={(e) => {
                    if (!rowUri || (!onInspect && !onOpenIndividual)) return
                    e.preventDefault()
                    setMenu({ x: e.clientX, y: e.clientY, uri: rowUri })
                  }}
                >
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
                          onInspect ? (
                            <button
                              onClick={() => onInspect(cell.uri!)}
                              className="max-w-full truncate font-mono text-[11px] text-workspace-accent hover:underline"
                              title={`Inspect ${cell.uri}`}
                            >
                              {cell.text}
                            </button>
                          ) : (
                            <span className="font-mono text-[11px] text-workspace-accent">{cell.text}</span>
                          )
                        ) : (
                          cell.text
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
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

      {menu &&
        createPortal(
          <div
            className="fixed z-50 min-w-[190px] rounded-md border bg-popover p-1 text-xs shadow-lg"
            style={{ left: menu.x, top: menu.y }}
            data-testid="explore-row-menu"
            onClick={(e) => e.stopPropagation()}
          >
            {onInspect && (
              <button
                onClick={() => {
                  onInspect(menu.uri)
                  setMenu(null)
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-accent"
                data-testid="explore-row-menu-inspect"
              >
                <PanelRight size={12} /> Inspect
              </button>
            )}
            {onOpenIndividual && (
              <button
                onClick={() => {
                  onOpenIndividual(menu.uri)
                  setMenu(null)
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-accent"
                data-testid="explore-row-menu-open"
              >
                <ExternalLink size={12} /> Open in Individuals view
              </button>
            )}
          </div>,
          document.body,
        )}
    </div>
  )
}
