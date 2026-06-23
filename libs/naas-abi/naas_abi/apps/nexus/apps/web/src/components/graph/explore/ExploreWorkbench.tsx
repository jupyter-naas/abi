'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, Check, Code, Copy, Download, FilterX, Loader2, Pencil, Plus, RefreshCw, RotateCcw, Save, Table2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  createView,
  getView,
  listViews,
  updateView,
  type SavedView,
  type SearchHit,
} from '@/lib/graph-query/client'
import { discoveredToColumns } from '@/lib/graph-query/columns'
import { specFromState, stateFromSpec, type ExploreState } from '@/lib/graph-query/explore-state'
import type { ViewQuerySpec } from '@/lib/graph-query/types'
import { BuilderPanel } from './BuilderPanel'
import { downloadCsv, rowsToCsv } from './csv'
import { ResultsTable } from './ResultsTable'
import { SaveViewDialog } from './SaveViewDialog'
import { SearchBar } from './SearchBar'
import { InstanceDrawer } from './InstanceDrawer'
import { useExplore } from './use-explore'

const DEFAULT_COLUMN_COUNT = 6

export interface ExploreWorkbenchProps {
  workspaceId: string
  /** When set (from ?view_id=), that saved view is loaded into the builder. */
  viewIdToLoad?: string | null
}

export function ExploreWorkbench({ workspaceId, viewIdToLoad }: ExploreWorkbenchProps) {
  const explore = useExplore(workspaceId)
  const { state, dispatch, discovered, result, running, error } = explore

  // ── Saved views ────────────────────────────────────────────────────────────
  // The views LIST lives in the left "Composer" submenu now; here we keep a copy only to
  // resolve the active view's name (toolbar badge) and known folders (Save dialog).
  const [views, setViews] = useState<SavedView[]>([])
  const [activeViewId, setActiveViewId] = useState<string | null>(null)
  // Signature of the state at the moment the active view was last loaded/saved. We diff the
  // live state against it to know whether the view has unsaved edits (drives the "Modified"
  // badge and whether "Update view" is enabled).
  const [savedSignature, setSavedSignature] = useState<string | null>(null)
  // The active saved view's description, captured on load and editable in place via the
  // description bar (so you can refine "what does this view answer?" without re-saving the spec).
  const [activeViewDescription, setActiveViewDescription] = useState('')
  const [editingDesc, setEditingDesc] = useState(false)
  const [descDraft, setDescDraft] = useState('')
  const [savingDesc, setSavingDesc] = useState(false)
  const [saveOpen, setSaveOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [showSparql, setShowSparql] = useState(false)
  const [copiedSparql, setCopiedSparql] = useState(false)
  const [exporting, setExporting] = useState(false)

  // ── Inspect drawer (click an individual in the table) ────────────────────────
  const router = useRouter()
  // History stack of inspected individual IRIs; the last is shown. Empty ⇒ drawer closed.
  const [inspectStack, setInspectStack] = useState<string[]>([])
  const openIndividualFull = useCallback(
    (uri: string) => {
      router.push(`/workspace/${workspaceId}/graph/individuals?selected=${encodeURIComponent(uri)}`)
    },
    [router, workspaceId],
  )

  const refreshViews = useCallback(() => {
    if (!workspaceId) return
    listViews({ workspaceId, path: '', recursive: true })
      .then((vs) => setViews(vs.filter((v) => v.kind === 'query')))
      .catch(() => setViews([]))
  }, [workspaceId])

  useEffect(refreshViews, [refreshViews])

  // After a save/update, refresh our own copy AND notify the left "Composer" submenu (a
  // separate React tree) via a window event so its views list stays in sync.
  const afterMutation = useCallback(() => {
    refreshViews()
    if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('views-changed'))
  }, [refreshViews])

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
        setActiveViewDescription(view.description ?? '')
        setEditingDesc(false)
        setSavedSignature(signatureOf(restored))
        setSaveError(null)
      } catch {
        /* ignore malformed view state */
      }
    },
    [dispatch, signatureOf],
  )

  // Load a saved view requested via ?view_id= (clicked in the left "Composer" submenu).
  const loadedParamRef = useRef<string | null>(null)
  useEffect(() => {
    if (!viewIdToLoad || !workspaceId) return
    if (loadedParamRef.current === viewIdToLoad) return
    loadedParamRef.current = viewIdToLoad
    getView(workspaceId, viewIdToLoad)
      .then((v) => loadView(v))
      .catch(() => {
        /* missing/forbidden view — stay on current state */
      })
  }, [viewIdToLoad, workspaceId, loadView])

  // Picking a search result starts a fresh ad-hoc exploration anchored on the hit (the class
  // becomes the grain; an individual also pins that instance). Additive to the graph + class
  // pickers below.
  const onPickSearchHit = useCallback(
    (hit: SearchHit) => {
      dispatch({
        type: 'setGrain',
        graphUris: [hit.graph_uri],
        classUri: hit.class_uri,
        classLabel: hit.class_label || hit.label,
        instanceUris: hit.kind === 'individual' ? [hit.uri] : undefined,
      })
      setActiveViewId(null)
      setActiveViewDescription('')
      setEditingDesc(false)
      setSavedSignature(null)
      setSaveError(null)
    },
    [dispatch],
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
    async (name: string, path: string, description: string) => {
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
          description: description || null,
          graphId: graphIdForUri(graphUri),
          graphUri,
          state: { spec: specFromState(state), spine: state.spine },
        })
        setActiveViewId(created.id ?? null)
        setActiveViewDescription(description)
        setEditingDesc(false)
        setSavedSignature(signatureOf(state))
        setSaveOpen(false)
        afterMutation()
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : 'Could not save view')
      } finally {
        setSaving(false)
      }
    },
    [afterMutation, graphIdForUri, signatureOf, state, workspaceId],
  )

  // Edit the loaded view's description in place (without touching the query spec).
  const onSaveDescription = useCallback(async () => {
    if (!activeViewId) return
    setSavingDesc(true)
    setSaveError(null)
    try {
      await updateView(activeViewId, { workspaceId, description: descDraft.trim() })
      setActiveViewDescription(descDraft.trim())
      setEditingDesc(false)
      afterMutation()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not save description')
    } finally {
      setSavingDesc(false)
    }
  }, [activeViewId, afterMutation, descDraft, workspaceId])

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
      afterMutation()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not update view')
    } finally {
      setUpdating(false)
    }
  }, [activeViewId, afterMutation, signatureOf, state, workspaceId])

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

  // Export the FULL result set (all pages, not just what's loaded in the table) as a CSV.
  const onExportCsv = useCallback(async () => {
    if (exporting) return
    setExporting(true)
    setSaveError(null)
    try {
      const data = await explore.fetchAllRows()
      if (!data || data.rows.length === 0) {
        setSaveError('Nothing to export.')
        return
      }
      const date = new Date().toISOString().slice(0, 10)
      const base = (activeViewName || 'explore').replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '') || 'explore'
      downloadCsv(`${base}_${date}.csv`, rowsToCsv(data.columns, data.rows))
    } catch {
      setSaveError('Could not export CSV.')
    } finally {
      setExporting(false)
    }
  }, [exporting, explore, activeViewName])

  return (
    <div className="flex h-full min-h-0 w-full flex-col" data-testid="explore-workbench">
      <div className="border-b px-4 py-2">
        <SearchBar workspaceId={workspaceId} graphUris={state.graphUris} onPick={onPickSearchHit} />
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-2 border-b px-4 py-2">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold">Composer</span>
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
                  setActiveViewDescription('')
                  setEditingDesc(false)
                  setSavedSignature(null)
                  setShowSparql(false)
                  // Drop ?view_id from the URL so the left menu deselects the view and only the
                  // Composer item stays highlighted. Reset the load guard so re-picking the same
                  // view in the menu reloads it.
                  loadedParamRef.current = null
                  if (viewIdToLoad) router.replace(`/workspace/${workspaceId}/graph/explore-next`)
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
              onClick={onExportCsv}
              disabled={!result || result.rows.length === 0 || running || exporting}
              className="flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
              data-testid="explore-export-csv"
              title="Export the full result set (all rows) as a CSV file"
            >
              {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} Export CSV
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

        {activeViewId && (
          <div
            className="flex items-start gap-2 border-b bg-muted/20 px-4 py-1.5 text-xs"
            data-testid="explore-view-description"
          >
            {editingDesc ? (
              <div className="flex w-full items-start gap-2">
                <textarea
                  value={descDraft}
                  onChange={(e) => setDescDraft(e.target.value)}
                  rows={2}
                  autoFocus
                  placeholder="What question does this view answer?"
                  className="flex-1 resize-y rounded border bg-background px-2 py-1 outline-none focus:ring-1 focus:ring-primary"
                  data-testid="explore-view-description-input"
                />
                <div className="flex shrink-0 flex-col gap-1">
                  <button
                    onClick={onSaveDescription}
                    disabled={savingDesc}
                    className="flex items-center justify-center gap-1 rounded bg-primary px-2 py-1 text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    data-testid="explore-view-description-save"
                  >
                    {savingDesc ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />} Save
                  </button>
                  <button
                    onClick={() => setEditingDesc(false)}
                    className="flex items-center justify-center gap-1 rounded border px-2 py-1 hover:bg-muted"
                  >
                    <X size={11} /> Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                <span className="mt-0.5 shrink-0 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  Description
                </span>
                <p
                  className={cn(
                    'flex-1 whitespace-pre-wrap',
                    !activeViewDescription && 'italic text-muted-foreground',
                  )}
                >
                  {activeViewDescription || 'No description yet.'}
                </p>
                <button
                  onClick={() => {
                    setDescDraft(activeViewDescription)
                    setEditingDesc(true)
                  }}
                  className="flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  data-testid="explore-view-description-edit"
                  title="Edit description"
                >
                  <Pencil size={11} /> Edit
                </button>
              </>
            )}
          </div>
        )}

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

        <div className="flex min-h-0 flex-1 overflow-hidden">
          <div className="relative min-h-0 flex-1 overflow-hidden">
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
                onInspect={(uri) => setInspectStack([uri])}
                onOpenIndividual={openIndividualFull}
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

          {inspectStack.length > 0 && (
            <InstanceDrawer
              workspaceId={workspaceId}
              trail={inspectStack}
              graphs={state.graphUris}
              onClose={() => setInspectStack([])}
              onOpenFull={openIndividualFull}
              onNavigate={(uri) => setInspectStack((s) => [...s, uri])}
              onJumpTo={(i) => setInspectStack((s) => s.slice(0, i + 1))}
            />
          )}
        </div>
      </div>

      {saveOpen && (
        <SaveViewDialog
          initialDescription={activeViewDescription}
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
