'use client'

import { useMemo, useRef, useState, useEffect } from 'react'
import { Check, ChevronDown, ChevronRight, CornerDownRight, GripVertical, Loader2, Plus, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { columnThroughPath, discoveredToColumn, expandedColumn } from '@/lib/graph-query/columns'
import { MAX_DRILL_DEPTH, type ExploreAction, type ExploreState } from '@/lib/graph-query/explore-state'
import { inversePathToAncestor } from '@/lib/graph-query/pipeline'
import type { Column, DiscoveredColumn, Hop, TargetClass } from '@/lib/graph-query/types'
import { Breadcrumb } from './Breadcrumb'
import { compactUri } from './format'
import type { ClassInfo, GraphPack } from './use-explore'

/** An earlier-grain level you can still pull columns from (reached via its inverse path). */
export interface AncestorGroup {
  index: number
  label: string
  classUri: string
  inversePath: Hop[]
}

/** The predicate a column reads (for matching against discovered columns). */
export function columnPredicate(col: Column): string {
  if (col.source.kind === 'property') return col.source.predicate
  if (col.source.kind === 'node') return col.source.path[0]?.predicate ?? ''
  return ''
}

export interface BuilderPanelProps {
  state: ExploreState
  dispatch: (action: ExploreAction) => void
  graphs: GraphPack[]
  graphsLoading: boolean
  classes: ClassInfo[]
  classesLoading: boolean
  discovered: DiscoveredColumn[]
  discoveredLoading: boolean
  /** Discover a target class's fields, for relation-expansion (2-hop columns). */
  loadFields: (classUri: string) => Promise<DiscoveredColumn[]>
}

export function BuilderPanel({
  state,
  dispatch,
  graphs,
  graphsLoading,
  classes,
  classesLoading,
  discovered,
  discoveredLoading,
  loadFields,
}: BuilderPanelProps) {
  const hasGraph = state.graphUris.length > 0
  const rootClass = state.spine[0]?.classUri ?? ''
  const grainClass = state.classUris[0] ?? ''

  // "Start from (class)" dropdown — sorted alphabetically by label.
  const sortedClasses = useMemo(
    () => [...classes].sort((a, b) => a.label.localeCompare(b.label)),
    [classes],
  )

  // Drag-to-reorder for the column chips (mirrors the table-header reorder).
  const [dragColId, setDragColId] = useState<string | null>(null)
  const [dragOverColId, setDragOverColId] = useState<string | null>(null)
  const [dragAfter, setDragAfter] = useState(false)
  const onChipDrop = (targetId: string, after: boolean) => {
    setDragOverColId(null)
    const dragged = dragColId
    setDragColId(null)
    if (!dragged || dragged === targetId) return
    const from = state.columns.findIndex((c) => c.id === dragged)
    let to = state.columns.findIndex((c) => c.id === targetId)
    if (from === -1 || to === -1) return
    if (from < to) to-- // post-removal coordinates
    dispatch({ type: 'reorderColumn', columnId: dragged, toIndex: after ? to + 1 : to })
  }

  const addedPredicates = useMemo(
    () => new Set(state.columns.map(columnPredicate)),
    [state.columns],
  )
  const available = useMemo(
    () => discovered.filter((d) => !addedPredicates.has(d.predicate_uri)),
    [discovered, addedPredicates],
  )
  // Relations the current grain can be followed into (need a known target class to re-anchor).
  const followable = useMemo(
    () => discovered.filter((d) => d.kind === 'relation' && d.target_classes.length > 0),
    [discovered],
  )
  // Every graph in the workspace — following a relation may cross into another graph (the
  // related class commonly lives elsewhere), so we widen the scope to span them all.
  const allGraphUris = useMemo(
    () => [...new Set(graphs.flatMap((p) => p.graphs.map((g) => g.uri)))],
    [graphs],
  )
  // Earlier levels in the drill path — their columns are still addable via the inverse path.
  const ancestors = useMemo<AncestorGroup[]>(
    () =>
      state.spine.slice(0, -1).map((node, i) => ({
        index: i,
        label: node.classLabel || compactUri(node.classUri),
        classUri: node.classUri,
        inversePath: inversePathToAncestor(state.spine, i),
      })),
    [state.spine],
  )

  return (
    <div className="flex flex-col gap-2 border-b bg-muted/30 px-4 py-3" data-testid="explore-builder">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Graphs">
          <GraphMultiSelect
            graphs={graphs}
            loading={graphsLoading}
            selected={state.graphUris}
            onToggle={(uri) => dispatch({ type: 'toggleGraph', graphUri: uri })}
          />
        </Field>

        <Field label="Start from (class)">
          <select
            value={rootClass}
            onChange={(e) => {
              const uri = e.target.value
              if (!uri) {
                dispatch({ type: 'setClasses', classUris: [] })
                return
              }
              const label = classes.find((c) => c.uri === uri)?.label ?? ''
              dispatch({ type: 'setRoot', classUri: uri, classLabel: label })
            }}
            data-testid="explore-class-select"
            disabled={!hasGraph || classesLoading}
            className="min-w-[200px] rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">{classesLoading ? 'Loading…' : 'Select a class'}</option>
            {sortedClasses.map((c) => (
              <option key={c.uri} value={c.uri}>
                {c.label} ({c.count.toLocaleString()})
              </option>
            ))}
          </select>
        </Field>
      </div>

      {state.instanceUris.length > 0 && (
        <div className="flex flex-wrap items-center gap-1" data-testid="explore-instance-pins">
          <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Pinned</span>
          {state.instanceUris.map((uri) => (
            <span
              key={uri}
              className="flex items-center gap-1 rounded border bg-background px-1.5 py-0.5 text-xs"
              title={uri}
            >
              <span className="max-w-[180px] truncate">{compactUri(uri)}</span>
              <button
                onClick={() =>
                  dispatch({ type: 'setInstances', instanceUris: state.instanceUris.filter((u) => u !== uri) })
                }
                className="text-muted-foreground hover:text-destructive"
                title="Unpin this instance"
              >
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}

      <Breadcrumb spine={state.spine} onDrillTo={(index) => dispatch({ type: 'drillTo', index })} />

      <div className="flex flex-col gap-1">
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Columns</span>
        <div className="flex flex-wrap items-center gap-1" data-testid="explore-columns">
          {state.columns.map((col, i) => (
            <span
              key={col.id}
              draggable
              onDragStart={(e) => {
                setDragColId(col.id)
                e.dataTransfer.effectAllowed = 'move'
              }}
              onDragOver={(e) => {
                e.preventDefault()
                e.dataTransfer.dropEffect = 'move'
                if (col.id === dragColId) return
                const r = e.currentTarget.getBoundingClientRect()
                setDragOverColId(col.id)
                setDragAfter(e.clientX > r.left + r.width / 2)
              }}
              onDragLeave={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOverColId(null)
              }}
              onDrop={(e) => {
                e.preventDefault()
                const r = e.currentTarget.getBoundingClientRect()
                onChipDrop(col.id, e.clientX > r.left + r.width / 2)
              }}
              onDragEnd={() => {
                setDragColId(null)
                setDragOverColId(null)
              }}
              data-testid={`explore-column-chip-${col.id}`}
              className={cn(
                'group flex cursor-grab items-center gap-1 rounded border bg-background px-1.5 py-0.5 text-xs',
                dragColId === col.id && 'opacity-40',
                dragOverColId === col.id && dragColId !== col.id && !dragAfter && 'border-l-2 border-l-workspace-accent',
                dragOverColId === col.id && dragColId !== col.id && dragAfter && 'border-r-2 border-r-workspace-accent',
              )}
            >
              <GripVertical size={10} className="text-muted-foreground/40" />
              <span className="max-w-[140px] truncate" title={col.label || col.id}>
                {col.label || col.id}
              </span>
              <button
                onClick={() => dispatch({ type: 'moveColumn', columnId: col.id, delta: -1 })}
                disabled={i === 0}
                className="text-muted-foreground hover:text-foreground disabled:opacity-30"
                title="Move left"
              >
                ‹
              </button>
              <button
                onClick={() => dispatch({ type: 'moveColumn', columnId: col.id, delta: 1 })}
                disabled={i === state.columns.length - 1}
                className="text-muted-foreground hover:text-foreground disabled:opacity-30"
                title="Move right"
              >
                ›
              </button>
              {col.source.kind !== 'aggregate' && (col.source.path?.length ?? 0) > 0 && (
                <select
                  value={col.source.collapse ?? 'concat'}
                  onChange={(e) =>
                    dispatch({ type: 'setColumnCollapse', columnId: col.id, collapse: e.target.value as 'concat' })
                  }
                  data-testid={`explore-collapse-${col.id}`}
                  className="rounded border bg-muted/40 px-0.5 text-[10px] text-muted-foreground outline-none"
                  title="How to show multiple related values in one row"
                >
                  <option value="concat">all</option>
                  <option value="first">first</option>
                  <option value="count">count</option>
                </select>
              )}
              <button
                onClick={() => dispatch({ type: 'removeColumn', columnId: col.id })}
                data-testid={`explore-column-remove-${col.id}`}
                className="text-muted-foreground hover:text-destructive"
                title="Remove"
              >
                <X size={11} />
              </button>
            </span>
          ))}
          <AddColumnMenu
            available={available}
            loading={discoveredLoading}
            disabled={!grainClass}
            onAdd={(dc) => dispatch({ type: 'addColumn', column: discoveredToColumn(dc) })}
            loadFields={loadFields}
            onAddExpanded={(rel, field) => dispatch({ type: 'addColumn', column: expandedColumn(rel, field) })}
            ancestors={ancestors}
            onAddAncestor={(anc, field) =>
              dispatch({ type: 'addColumn', column: columnThroughPath(field, anc.inversePath, anc.label) })
            }
          />
          <FollowMenu
            relations={followable}
            loading={discoveredLoading}
            disabled={!grainClass}
            atMaxDepth={state.spine.length >= MAX_DRILL_DEPTH}
            onFollow={(dc, target) =>
              dispatch({
                type: 'follow',
                via: { predicate: dc.predicate_uri, direction: dc.direction, label: dc.label },
                targetClassUri: target.uri,
                targetClassLabel: target.label,
                graphUris: allGraphUris,
              })
            }
          />
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      {children}
    </label>
  )
}

/** Multi-select graph picker — pick one or several graphs to build cross-graph views. */
function GraphMultiSelect({
  graphs,
  loading,
  selected,
  onToggle,
}: {
  graphs: GraphPack[]
  loading: boolean
  selected: string[]
  onToggle: (uri: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const allGraphs = useMemo(() => graphs.flatMap((p) => p.graphs), [graphs])
  const summary = loading
    ? 'Loading…'
    : selected.length === 0
      ? 'Select graphs'
      : selected.length === 1
        ? allGraphs.find((g) => g.uri === selected[0])?.label ?? compactUri(selected[0])
        : `${selected.length} graphs`

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        disabled={loading}
        data-testid="explore-graph-select"
        className="flex min-w-[180px] items-center justify-between gap-2 rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
      >
        <span className="truncate">{summary}</span>
        <ChevronDown size={12} className="shrink-0 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 max-h-72 w-72 overflow-y-auto rounded-md border bg-background py-1 shadow-lg">
          {allGraphs.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">No graphs</p>
          ) : (
            graphs.map((pack) => (
              <div key={pack.role_label}>
                <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">
                  {pack.role_label}
                </div>
                {pack.graphs.map((g) => {
                  const checked = selected.includes(g.uri)
                  return (
                    <button
                      key={g.uri}
                      onClick={() => onToggle(g.uri)}
                      data-testid={`explore-graph-option-${g.id}`}
                      className="flex w-full items-center gap-2 px-3 py-1 text-left text-xs hover:bg-muted"
                    >
                      <span
                        className={cn(
                          'flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border',
                          checked ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/40',
                        )}
                      >
                        {checked && <Check size={10} />}
                      </span>
                      <span className="flex-1 truncate">{g.label}</span>
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

function AddColumnMenu({
  available,
  loading,
  disabled,
  onAdd,
  loadFields,
  onAddExpanded,
  ancestors,
  onAddAncestor,
}: {
  available: DiscoveredColumn[]
  loading: boolean
  disabled: boolean
  onAdd: (dc: DiscoveredColumn) => void
  loadFields: (classUri: string) => Promise<DiscoveredColumn[]>
  onAddExpanded: (relation: DiscoveredColumn, field: DiscoveredColumn) => void
  ancestors: AncestorGroup[]
  onAddAncestor: (ancestor: AncestorGroup, field: DiscoveredColumn) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [fields, setFields] = useState<Record<string, DiscoveredColumn[]>>({})
  const [fieldsLoading, setFieldsLoading] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const filtered = useMemo(() => {
    const t = search.trim().toLowerCase()
    if (!t) return available
    return available.filter((d) => d.label.toLowerCase().includes(t) || d.predicate_uri.toLowerCase().includes(t))
  }, [available, search])

  const close = () => {
    setOpen(false)
    setSearch('')
    setExpanded(null)
  }

  const toggleExpand = (key: string, classUri: string) => {
    if (expanded === key) {
      setExpanded(null)
      return
    }
    setExpanded(key)
    if (!fields[key]) {
      setFieldsLoading(key)
      loadFields(classUri)
        .then((cols) => setFields((prev) => ({ ...prev, [key]: cols })))
        .catch(() => setFields((prev) => ({ ...prev, [key]: [] })))
        .finally(() => setFieldsLoading((cur) => (cur === key ? null : cur)))
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        disabled={disabled}
        data-testid="explore-add-column"
        className={cn(
          'flex items-center gap-1 rounded border border-dashed px-1.5 py-0.5 text-xs',
          disabled ? 'cursor-not-allowed opacity-40' : 'hover:bg-muted',
        )}
      >
        <Plus size={11} /> Add column
        <ChevronDown size={11} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 w-80 overflow-hidden rounded-md border bg-background shadow-lg">
          <div className="border-b p-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search columns…"
              data-testid="explore-add-column-search"
              className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
              autoFocus
            />
          </div>
          <div className="max-h-72 overflow-y-auto py-1">
            {loading ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">Loading columns…</p>
            ) : filtered.length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">No more columns</p>
            ) : (
              filtered.map((d) => {
                const isRelation = d.kind === 'relation' && d.target_classes.length > 0
                const isOpen = expanded === d.id
                return (
                  <div key={`${d.predicate_uri}:${d.direction}`}>
                    <div className="flex w-full items-center gap-1 px-2 text-xs hover:bg-muted">
                      <button
                        onClick={() => {
                          onAdd(d)
                          close()
                        }}
                        data-testid={`explore-add-column-option-${d.id}`}
                        className="flex flex-1 items-center justify-between gap-2 py-1.5 text-left"
                        title={d.predicate_uri}
                      >
                        <span className="flex items-center gap-1.5">
                          <span
                            className={cn(
                              'rounded px-1 text-[9px] uppercase',
                              d.kind === 'relation' ? 'bg-blue-500/15 text-blue-600' : 'bg-muted text-muted-foreground',
                            )}
                          >
                            {d.kind === 'relation' ? 'rel' : d.datatype}
                          </span>
                          <span className="max-w-[150px] truncate">{d.label}</span>
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {d.instance_count > 0 ? d.instance_count.toLocaleString() : d.source === 'ontology' ? '0' : ''}
                        </span>
                      </button>
                      {isRelation && (
                        <button
                          onClick={() => toggleExpand(d.id, d.target_classes[0].uri)}
                          data-testid={`explore-expand-${d.id}`}
                          className="rounded p-0.5 text-muted-foreground hover:bg-muted-foreground/20"
                          title={`Add a field from ${d.target_classes[0].label}`}
                        >
                          {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        </button>
                      )}
                    </div>
                    {isRelation && isOpen && (
                      <div className="border-l-2 border-blue-500/20 bg-muted/30 py-0.5 pl-3" data-testid={`explore-fields-${d.id}`}>
                        {fieldsLoading === d.id ? (
                          <p className="flex items-center gap-1.5 px-3 py-1 text-[11px] text-muted-foreground">
                            <Loader2 size={11} className="animate-spin" /> Loading {d.target_classes[0].label}…
                          </p>
                        ) : (fields[d.id]?.length ?? 0) === 0 ? (
                          <p className="px-3 py-1 text-[11px] text-muted-foreground">No fields</p>
                        ) : (
                          fields[d.id].map((f) => (
                            <button
                              key={`${f.predicate_uri}:${f.direction}`}
                              onClick={() => {
                                onAddExpanded(d, f)
                                close()
                              }}
                              data-testid={`explore-add-field-${d.id}-${f.id}`}
                              className="flex w-full items-center justify-between gap-2 px-3 py-1 text-left text-[11px] hover:bg-muted"
                            >
                              <span className="flex items-center gap-1.5">
                                <span className="rounded bg-muted px-1 text-[9px] uppercase text-muted-foreground">
                                  {f.kind === 'relation' ? 'rel' : f.datatype}
                                </span>
                                <span className="max-w-[160px] truncate">{f.label}</span>
                              </span>
                              <span className="text-[10px] text-muted-foreground">{f.instance_count.toLocaleString()}</span>
                            </button>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                )
              })
            )}

            {ancestors.length > 0 && (
              <div className="mt-1 border-t pt-1">
                <div className="px-3 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  From earlier levels
                </div>
                {ancestors.map((anc) => {
                  const key = `anc:${anc.index}`
                  const isOpen = expanded === key
                  return (
                    <div key={key}>
                      <button
                        onClick={() => toggleExpand(key, anc.classUri)}
                        data-testid={`explore-ancestor-${anc.index}`}
                        className="flex w-full items-center gap-1 px-2 py-1.5 text-left text-xs hover:bg-muted"
                      >
                        {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        <span className="text-muted-foreground">{anc.label}</span>
                      </button>
                      {isOpen && (
                        <div className="border-l-2 border-amber-500/20 bg-muted/30 py-0.5 pl-3">
                          {fieldsLoading === key ? (
                            <p className="flex items-center gap-1.5 px-3 py-1 text-[11px] text-muted-foreground">
                              <Loader2 size={11} className="animate-spin" /> Loading {anc.label}…
                            </p>
                          ) : (fields[key]?.length ?? 0) === 0 ? (
                            <p className="px-3 py-1 text-[11px] text-muted-foreground">No fields</p>
                          ) : (
                            fields[key].map((f) => (
                              <button
                                key={`${f.predicate_uri}:${f.direction}`}
                                onClick={() => {
                                  onAddAncestor(anc, f)
                                  close()
                                }}
                                data-testid={`explore-add-ancestor-${anc.index}-${f.id}`}
                                className="flex w-full items-center justify-between gap-2 px-3 py-1 text-left text-[11px] hover:bg-muted"
                              >
                                <span className="flex items-center gap-1.5">
                                  <span className="rounded bg-muted px-1 text-[9px] uppercase text-muted-foreground">
                                    {f.kind === 'relation' ? 'rel' : f.datatype}
                                  </span>
                                  <span className="max-w-[160px] truncate">{f.label}</span>
                                </span>
                                <span className="text-[10px] text-muted-foreground">{f.instance_count.toLocaleString()}</span>
                              </button>
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function FollowMenu({
  relations,
  loading,
  disabled,
  atMaxDepth,
  onFollow,
}: {
  relations: DiscoveredColumn[]
  loading: boolean
  disabled: boolean
  atMaxDepth: boolean
  onFollow: (dc: DiscoveredColumn, target: TargetClass) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const blocked = disabled || atMaxDepth
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        disabled={blocked}
        data-testid="explore-follow"
        className={cn(
          'flex items-center gap-1 rounded border border-dashed px-1.5 py-0.5 text-xs',
          blocked ? 'cursor-not-allowed opacity-40' : 'hover:bg-muted',
        )}
        title={atMaxDepth ? 'Max drill depth reached' : 'Follow a relation — the rows become the related type'}
      >
        <CornerDownRight size={11} /> Follow
        <ChevronDown size={11} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 w-80 overflow-hidden rounded-md border bg-background shadow-lg">
          <div className="border-b px-3 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            Drill into a related type
          </div>
          <div className="max-h-64 overflow-y-auto py-1">
            {atMaxDepth ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">
                Max drill depth reached — remove a level to follow further.
              </p>
            ) : loading ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">Loading relations…</p>
            ) : relations.length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">No relations to follow from here</p>
            ) : (
              relations.flatMap((dc) =>
                dc.target_classes.map((t) => (
                  <button
                    key={`${dc.predicate_uri}:${t.uri}`}
                    onClick={() => {
                      onFollow(dc, t)
                      setOpen(false)
                    }}
                    data-testid={`explore-follow-option-${dc.id}`}
                    className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-muted"
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="text-muted-foreground">{dc.label}</span>
                      <CornerDownRight size={10} className="text-muted-foreground/60" />
                      <span className="font-medium">{t.label}</span>
                    </span>
                    <span className="text-[10px] text-muted-foreground">{t.instance_count.toLocaleString()}</span>
                  </button>
                )),
              )
            )}
          </div>
        </div>
      )}
    </div>
  )
}
