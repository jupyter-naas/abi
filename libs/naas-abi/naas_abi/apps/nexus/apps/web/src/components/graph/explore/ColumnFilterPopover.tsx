'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  LIST_OPERATORS,
  NULLARY_OPERATORS,
  OPERATOR_LABELS,
  RANGE_OPERATORS,
  operatorsFor,
} from '@/lib/graph-query/columns'
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters'
import type { Datatype, FacetBucket, Operator } from '@/lib/graph-query/types'

const FACET_DEBOUNCE_MS = 250

export interface ColumnFilterPopoverProps {
  columnId: string
  label: string
  datatype: Datatype
  facetable: boolean
  /** Viewport coordinates of the trigger (the popover is portalled to escape table clipping). */
  anchor: { left: number; top: number }
  state: ColumnFilterState | undefined
  onChange: (state: ColumnFilterState) => void
  onClear: () => void
  loadFacets: (columnId: string, search: string) => Promise<FacetBucket[]>
  onClose: () => void
}

const POPOVER_WIDTH = 288

/** Excel-style per-column filter: facet checkboxes + a free-form condition row. */
export function ColumnFilterPopover({
  columnId,
  label,
  datatype,
  facetable,
  anchor,
  state,
  onChange,
  onClear,
  loadFacets,
  onClose,
}: ColumnFilterPopoverProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [search, setSearch] = useState('')
  const [buckets, setBuckets] = useState<FacetBucket[]>([])
  const [facetsLoading, setFacetsLoading] = useState(false)
  const [facetsError, setFacetsError] = useState<string | null>(null)

  const selected = useMemo(() => new Set(state?.selected ?? []), [state?.selected])
  const operator = state?.operator
  const value = state?.value

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      const target = e.target as Element
      // Ignore clicks on a filter trigger button — it owns its own open/close toggle.
      if (ref.current && !ref.current.contains(target) && !target.closest?.('[data-filter-trigger]')) onClose()
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [onClose])

  // Fetch facets (debounced) when facetable. Non-facetable columns rely on the condition row.
  useEffect(() => {
    if (!facetable) return
    let cancelled = false
    setFacetsLoading(true)
    setFacetsError(null)
    const handle = setTimeout(() => {
      loadFacets(columnId, search)
        .then((b) => {
          if (!cancelled) setBuckets(b)
        })
        .catch(() => {
          if (!cancelled) setFacetsError('Could not load values')
        })
        .finally(() => {
          if (!cancelled) setFacetsLoading(false)
        })
    }, FACET_DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(handle)
    }
  }, [columnId, search, facetable, loadFacets])

  const toggleValue = (v: string) => {
    const next = new Set(selected)
    if (next.has(v)) next.delete(v)
    else next.add(v)
    onChange({ ...state, selected: [...next] })
  }

  const setOperator = (op: Operator | '') => {
    if (op === '') {
      onChange({ ...state, operator: undefined, value: undefined })
      return
    }
    // Reset the value shape when switching operator families.
    let nextValue = value
    if (NULLARY_OPERATORS.has(op)) nextValue = undefined
    else if (RANGE_OPERATORS.has(op)) nextValue = ['', '']
    else if (LIST_OPERATORS.has(op)) nextValue = []
    else if (Array.isArray(value)) nextValue = ''
    onChange({ ...state, operator: op, value: nextValue ?? '' })
  }

  const conditionOps = operatorsFor(datatype)
  const isRange = operator ? RANGE_OPERATORS.has(operator) : false
  const isNullary = operator ? NULLARY_OPERATORS.has(operator) : false
  const showValueInput = !!operator && !isNullary && !(operator && LIST_OPERATORS.has(operator))

  if (typeof document === 'undefined') return null
  // Clamp into the viewport so the popover (and its condition input) is never off-screen.
  const left = Math.max(8, Math.min(anchor.left, window.innerWidth - POPOVER_WIDTH - 8))
  const maxHeight = Math.max(200, window.innerHeight - anchor.top - 16)

  return createPortal(
    <div
      ref={ref}
      data-testid={`column-filter-popover-${columnId}`}
      style={{ position: 'fixed', left, top: anchor.top, width: POPOVER_WIDTH, maxHeight }}
      className="z-50 flex flex-col overflow-y-auto rounded-md border bg-background text-foreground shadow-lg"
    >
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="truncate text-xs font-semibold" title={label}>
          {label}
        </span>
        {!isBlank(state) && (
          <button
            onClick={onClear}
            data-testid={`column-filter-clear-${columnId}`}
            className="flex items-center gap-1 rounded px-1 py-0.5 text-[10px] text-muted-foreground hover:bg-muted"
          >
            <X size={10} /> Clear
          </button>
        )}
      </div>

      {facetable && (
        <>
          <div className="border-b p-2">
            <div className="relative">
              <Search
                size={12}
                className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search values…"
                data-testid={`column-filter-search-${columnId}`}
                className="w-full rounded border bg-background py-1 pl-7 pr-2 text-xs outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
          <div className="max-h-48 overflow-y-auto py-1" data-testid={`column-filter-values-${columnId}`}>
            {facetsLoading ? (
              <p className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                <Loader2 size={12} className="animate-spin" /> Loading…
              </p>
            ) : facetsError ? (
              <p className="px-3 py-2 text-xs text-destructive">{facetsError}</p>
            ) : buckets.length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">No values</p>
            ) : (
              buckets.map((b) => {
                const checked = selected.has(b.value)
                return (
                  <label
                    key={b.value}
                    className="flex cursor-pointer items-center gap-2 px-3 py-1 text-xs hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleValue(b.value)}
                      className="h-3 w-3"
                    />
                    <span className="flex-1 truncate" title={b.value}>
                      {b.value || <em className="text-muted-foreground">empty</em>}
                    </span>
                    <span className="text-[10px] text-muted-foreground">{b.count}</span>
                  </label>
                )
              })
            )}
          </div>
        </>
      )}

      {/* Free-form condition row */}
      <div className="space-y-2 border-t p-2">
        <select
          value={operator ?? ''}
          onChange={(e) => setOperator(e.target.value as Operator | '')}
          data-testid={`column-filter-operator-${columnId}`}
          className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">No condition</option>
          {conditionOps.map((op) => (
            <option key={op} value={op}>
              {OPERATOR_LABELS[op]}
            </option>
          ))}
        </select>

        {showValueInput && !isRange && (
          <input
            value={typeof value === 'string' || typeof value === 'number' ? String(value) : ''}
            onChange={(e) => onChange({ ...state, value: e.target.value })}
            placeholder="Value…"
            data-testid={`column-filter-value-${columnId}`}
            className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
          />
        )}
        {showValueInput && isRange && (
          <div className="flex items-center gap-1">
            <input
              value={Array.isArray(value) ? String(value[0] ?? '') : ''}
              onChange={(e) =>
                onChange({ ...state, value: [e.target.value, Array.isArray(value) ? value[1] ?? '' : ''] })
              }
              placeholder="From"
              data-testid={`column-filter-from-${columnId}`}
              className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
            />
            <span className="text-xs text-muted-foreground">–</span>
            <input
              value={Array.isArray(value) ? String(value[1] ?? '') : ''}
              onChange={(e) =>
                onChange({ ...state, value: [Array.isArray(value) ? value[0] ?? '' : '', e.target.value] })
              }
              placeholder="To"
              data-testid={`column-filter-to-${columnId}`}
              className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
