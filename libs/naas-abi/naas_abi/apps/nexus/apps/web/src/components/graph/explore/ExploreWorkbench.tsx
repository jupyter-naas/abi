'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, Check, Code, Copy, FilterX, Loader2, Plus, RefreshCw, RotateCcw, Save, Table2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  createView,
  deleteView as apiDeleteView,
  listViews,
  updateView,
  type SavedView,
} from '@/lib/graph-query/client'
import { discoveredToColumns } from '@/lib/graph-query/columns'
import { specFromState, stateFromSpec, type ExploreState } from '@/lib/graph-query/explore-state'
import type { ViewQuerySpec } from '@/lib/graph-query/types'
import { BuilderPanel } from './BuilderPanel'
import { ResultsTable } from './ResultsTable'
import { SaveViewDialog } from './SaveViewDialog'
import { useExplore } from './use-explore'
import { ViewsSidebar } from './ViewsSidebar'

const DEFAULT_COLUMN_COUNT = 6

export interface ExploreWorkbenchProps {
  workspaceId: string
}

export function ExploreWorkbench({ workspaceId }: ExploreWorkbenchProps) {
  const explore = useExplore(workspaceId)
  const { state, dispatch, discovered, result, running, error } = explore

  // ── Saved views ────────────────────────────────────────────────────────────
  const [views, setViews] = useState<SavedView[]>([])
  const [viewsLoading, setViewsLoading] = useState(false)
  const [activeViewId, setActiveViewId] = useState<string | null>(null)
  // Signature of the state at the moment the active view was last loaded/saved. We diff the
  // live state against it to know whether the view has unsaved edits (drives the "Modified"
  // badge and whether "Update view" is enabled).
  const [savedSignature, setSavedSignature] = useState<string | null>(null)
  const [saveOpen, setSaveOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [showSparql, setShowSparql] = useState(false)
  const [copiedSparql, setCopiedSparql] = useState(false)

  const refreshViews = useCallback(() => {
    if (!workspaceId) return
    setViewsLoading(true)
    listViews({ workspaceId, path: '', recursive: true })
      .then((vs) => setViews(vs.filter((v) => v.kind === 'query')))
      .catch(() => setViews([]))
      .finally(() => setViewsLoading(false))
  }, [workspaceId])

  useEffect(refreshViews, [refreshViews])

  // ── Auto-seed default columns once per anchor ────────────────────────────────
  // On the first class pick, seed a few default columns. After a drill the carried columns
  // are already present, so we append the new grain's defaults (deduping ids) — you keep the
  // columns from earlier levels AND get the grain's own.
  const anchorKey = `${state.graphUris.join('|')}::${state.classUris.join('|')}`
  const seededAnchor = useRef<string | null>(null)
  useEffect(() => {
    // Only seed once the discovered columns belong to the CURRENT grain (never a previous
    // grain's columns still in flight after a drill).
    if (explore.discoveredFor !== anchorKey) return
    if (discovered.length === 0 || state.classUris.length === 0) return
    if (seededAnchor.current === anchorKey) return
    // Auto-seed default columns ONLY at the root (initial class pick). After a drill we keep
    // exactly the columns carried from the prior level — no surprise extra columns / duplicates.
    if (state.spine.length <= 1 && state.columns.length === 0) {
      dispatch({ type: 'setColumns', columns: discoveredToColumns(discovered.slice(0, DEFAULT_COLUMN_COUNT)) })
    }
    seededAnchor.current = anchorKey
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [discovered, explore.discoveredFor, anchorKey])

  // Columns the filter popover may facet (list mode, dimension columns only).
  const facetableById = useMemo(() => {
    const map: Record<string, boolean> = {}
    if (state.mode !== 'list') return map
    const byId = new Map(discovered.map((d) => [d.id, d]))
    for (const col of state.columns) {
      const d = byId.get(col.id)
      map[col.id] = d ? d.facetable : col.source.kind !== 'aggregate'
    }
    return map
  }, [discovered, state.columns, state.mode])

  // Serialized signature of the editable state (compiled spec + drill breadcrumb). Compared
  // against the signature captured when the active view was loaded/saved to detect edits.
  const signatureOf = useCallback((s: ExploreState): string => {
    try {
      return JSON.stringify({ spec: specFromState(s), spine: s.spine })
    } catch {
      return ''
    }
  }, [])
  const currentSignature = useMemo(() => signatureOf(state), [signatureOf, state])

  // ── View load / save / delete ────────────────────────────────────────────────
  const loadView = useCallback(
    (view: SavedView) => {
      try {
        // State is stored as { spec, spine? }; tolerate a legacy bare-spec shape too.
        const stored = (view.state ?? {}) as { spec?: ViewQuerySpec; spine?: unknown[] }
        const spec = stored.spec ?? ('mode' in (view.state ?? {}) ? (view.state as unknown as ViewQuerySpec) : null)
        if (!spec || !('mode' in spec)) return
        const grain =
          spec.mode === 'list'
            ? spec.root.kind === 'class'
              ? spec.root.class_uris.join('|')
              : ''
            : spec.fact.kind === 'class'
              ? spec.fact.class_uris.join('|')
              : ''
        seededAnchor.current = `${spec.graph_uris.join('|')}::${grain}`
        const base = stateFromSpec(spec)
        // Restore the drill breadcrumb when it was persisted (keeps spec lowering identical).
        const restored =
          Array.isArray(stored.spine) && stored.spine.length > 0
            ? { ...base, spine: stored.spine as ExploreState['spine'] }
            : base
        dispatch({ type: 'load', state: restored })
        setActiveViewId(view.id)
        setSavedSignature(signatureOf(restored))
        setSaveError(null)
      } catch {
        /* ignore malformed view state */
      }
    },
    [dispatch, signatureOf],
  )

  const graphIdForUri = useCallback(
    (uri: string): string => {
      for (const pack of explore.graphs) {
        const g = pack.graphs.find((x) => x.uri === uri)
        if (g) return g.id
      }
      return uri
    },
    [explore.graphs],
  )

  const onSave = useCallback(
    async (name: string, path: string) => {
      const graphUri = state.graphUris[0]
      if (!graphUri) {
        setSaveError('Select a graph first.')
        return
      }
      setSaving(true)
      setSaveError(null)
      try {
        const created = await createView({
          workspaceId,
          name,
          path,
          graphId: graphIdForUri(graphUri),
          graphUri,
          state: { spec: specFromState(state), spine: state.spine },
        })
        setActiveViewId(created.id ?? null)
        setSavedSignature(signatureOf(state))
        setSaveOpen(false)
        refreshViews()
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : 'Could not save view')
      } finally {
        setSaving(false)
      }
    },
    [graphIdForUri, refreshViews, signatureOf, state, workspaceId],
  )

  // Overwrite the currently-loaded view in place with the live state.
  const onUpdate = useCallback(async () => {
    if (!activeViewId) return
    setUpdating(true)
    setSaveError(null)
    try {
      await updateView(activeViewId, {
        workspaceId,
        state: { spec: specFromState(state), spine: state.spine },
      })
      setSavedSignature(signatureOf(state))
      refreshViews()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not update view')
    } finally {
      setUpdating(false)
    }
  }, [activeViewId, refreshViews, signatureOf, state, workspaceId])

  const onDelete = useCallback(
    async (view: SavedView) => {
      try {
        await apiDeleteView(workspaceId, view.id)
        if (activeViewId === view.id) {
          setActiveViewId(null)
          setSavedSignature(null)
        }
        refreshViews()
      } catch {
        /* surfaced via refresh */
      }
    },
    [activeViewId, refreshViews, workspaceId],
  )

  const canSave = state.graphUris.length > 0 && state.classUris.length > 0
  const busy = running || explore.discoveredLoading || explore.classesLoading
  const hasFilters = Object.keys(state.filters).length > 0
  const activeView = useMemo(
    () => views.find((v) => v.id === activeViewId) ?? null,
    [views, activeViewId],
  )
  const activeViewName = activeView?.name ?? activeView?.label ?? null
  // A view is "dirty" once the live state diverges from the signature captured on load/save.
  const dirty = activeViewId != null && savedSignature != null && currentSignature !== savedSignature

  return (
    <div className="flex h-full min-h-0 w-full" data-testid="explore-workbench">
      <ViewsSidebar
        views={views}
        loading={viewsLoading}
        activeViewId={activeViewId}
        onLoad={loadView}
        onDelete={onDelete}
        onRefresh={refreshViews}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-2 border-b px-4 py-2">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold">Explore</span>
            {result && !busy && (
              <span className="text-xs text-muted-foreground" data-testid="explore-total">
                {result.count.total.toLocaleString()} {result.mode === 'aggregate' ? 'groups' : 'rows'}
              </span>
            )}
            {busy && (
              <span className="flex items-center gap-1.5 text-xs text-workspace-accent" data-testid="explore-busy">
                <Loader2 size={13} className="animate-spin" />
                {running ? 'Running query…' : explore.discoveredLoading ? 'Loading columns…' : 'Loading…'}
              </span>
            )}
            {activeView && (
              <span
                className="flex items-center gap-1.5 rounded-full border bg-background px-2 py-0.5 text-xs"
                data-testid="explore-active-view"
                title={dirty ? 'This view has unsaved changes' : 'Viewing a saved view'}
              >
                <Table2 size={12} className="text-workspace-accent" />
                <span className="max-w-[180px] truncate font-medium">{activeViewName}</span>
                {dirty ? (
                  <span className="flex items-center gap-1 text-amber-600 dark:text-amber-500">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> Modified
                  </span>
                ) : (
                  <span className="text-muted-foreground">Saved</span>
                )}
              </span>
            )}
            {saveError && !saveOpen && (
              <span className="text-xs text-destructive" data-testid="explore-view-error">
                {saveError}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {hasFilters && (
              <button
                onClick={() => dispatch({ type: 'clearAllFilters' })}
                className="flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-muted"
                data-testid="explore-clear-filters"
                title="Remove all column filters"
              >
                <FilterX size={12} /> Clear filters
              </button>
            )}
            {(state.graphUris.length > 0 || activeViewId) && (
              <button
                onClick={() => {
                  dispatch({ type: 'reset' })
                  setActiveViewId(null)
                  setShowSparql(false)
                }}
                className="flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-muted"
                data-testid="explore-reset"
                title="Start over (clear graph, columns and filters)"
              >
                <RotateCcw size={12} /> Reset
              </button>
            )}
            <button
              onClick={() => setShowSparql((p) => !p)}
              disabled={!result?.resolved_sparql}
              className={cn(
                'flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50',
                showSparql && 'bg-muted text-workspace-accent',
              )}
              data-testid="explore-sparql-toggle"
              title="Show the SPARQL the backend executed"
            >
              <Code size={12} /> SPARQL
            </button>
            <button
              onClick={explore.refresh}
              disabled={!explore.runnable || running}
              className="flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
              data-testid="explore-refresh"
            >
              {running ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              Refresh
            </button>
            {activeViewId ? (
              <>
                <button
                  onClick={onUpdate}
                  disabled={!canSave || updating || !dirty}
                  className="flex items-center gap-1 rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  data-testid="explore-update-view"
                  title={dirty ? 'Save changes to this view' : 'No unsaved changes'}
                >
                  {updating ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Update view
                </button>
                <button
                  onClick={() => {
                    setSaveError(null)
                    setSaveOpen(true)
                  }}
                  disabled={!canSave}
                  className="flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
                  data-testid="explore-save-as"
                  title="Save as a new view"
                >
                  <Plus size={12} /> Save as
                </button>
              </>
            ) : (
              <button
                onClick={() => {
                  setSaveError(null)
                  setSaveOpen(true)
                }}
                disabled={!canSave}
                className="flex items-center gap-1 rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                data-testid="explore-save"
              >
                <Save size={12} /> Save view
              </button>
            )}
          </div>
        </div>

        <BuilderPanel
          state={state}
          dispatch={dispatch}
          graphs={explore.graphs}
          graphsLoading={explore.graphsLoading}
          classes={explore.classes}
          classesLoading={explore.classesLoading}
          discovered={discovered}
          discoveredLoading={explore.discoveredLoading}
          loadFields={explore.discoverColumnsFor}
        />

        {error && (
          <div
            className="flex items-center gap-2 border-b bg-destructive/10 px-4 py-2 text-xs text-destructive"
            data-testid="explore-error"
          >
            <AlertCircle size={13} /> {error}
          </div>
        )}

        {showSparql && result?.resolved_sparql && (
          <div className="border-b bg-muted/30" data-testid="explore-sparql-panel">
            <div className="flex items-center justify-between px-4 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              <span>Executed SPARQL</span>
              <button
                onClick={() => {
                  navigator.clipboard?.writeText(result.resolved_sparql ?? '')
                  setCopiedSparql(true)
                  setTimeout(() => setCopiedSparql(false), 1500)
                }}
                className="flex items-center gap-1 rounded px-1 py-0.5 normal-case hover:bg-muted"
              >
                {copiedSparql ? <Check size={11} /> : <Copy size={11} />} {copiedSparql ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre className="max-h-44 overflow-auto px-4 pb-2 font-mono text-[11px] leading-relaxed">
              {result.resolved_sparql}
            </pre>
          </div>
        )}

        <div className="min-h-0 flex-1">
          {result ? (
            <ResultsTable
              result={result}
              state={state}
              dispatch={dispatch}
              running={running}
              rowsLoadingMore={explore.rowsLoadingMore}
              facetableById={facetableById}
              loadFacets={explore.loadColumnFacets}
              onLoadMore={explore.loadMore}
            />
          ) : (
            <div
              className={cn('flex h-full items-center justify-center text-sm text-muted-foreground')}
              data-testid="explore-placeholder"
            >
              {running ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="animate-spin" /> Running…
                </span>
              ) : !canSave ? (
                'Pick a graph and a class to start exploring.'
              ) : state.columns.length === 0 ? (
                'Add a column to see results.'
              ) : (
                'Building query…'
              )}
            </div>
          )}
        </div>
      </div>

      {saveOpen && (
        <SaveViewDialog
          knownFolders={[...new Set(views.map((v) => v.path).filter(Boolean))]}
          saving={saving}
          error={saveError}
          onCancel={() => setSaveOpen(false)}
          onSave={onSave}
        />
      )}
    </div>
  )
}
