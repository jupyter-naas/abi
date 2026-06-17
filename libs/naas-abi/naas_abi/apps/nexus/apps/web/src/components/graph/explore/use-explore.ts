'use client'

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { authFetch } from '@/stores/auth'
import { discoveredToColumns } from '@/lib/graph-query/columns'
import {
  fetchColumns,
  fetchFacets,
  GraphApiError,
  runQuery,
} from '@/lib/graph-query/client'
import {
  exploreReducer,
  initialExploreState,
  specFromState,
  type ExploreAction,
  type ExploreState,
} from '@/lib/graph-query/explore-state'
import { isRunnable } from '@/lib/graph-query/spec'
import type {
  DiscoveredColumn,
  FacetBucket,
  GraphQueryResponse,
  ListSpec,
} from '@/lib/graph-query/types'

// ── Graph / class discovery (reuses the existing discovery endpoints) ────────────

export interface GraphInfo {
  id: string
  uri: string
  label: string
  role_label: string
}
export interface GraphPack {
  role_label: string
  graphs: GraphInfo[]
}
export interface ClassInfo {
  uri: string
  label: string
  count: number
}

async function getJson<T>(path: string): Promise<T> {
  const res = await authFetch(path)
  if (!res.ok) throw new GraphApiError(res.status, `Request failed (${res.status})`)
  return (await res.json()) as T
}

const AUTORUN_DEBOUNCE_MS = 350

export interface UseExplore {
  state: ExploreState
  dispatch: (action: ExploreAction) => void

  graphs: GraphPack[]
  graphsLoading: boolean
  classes: ClassInfo[]
  classesLoading: boolean

  discovered: DiscoveredColumn[]
  discoveredLoading: boolean
  /** Anchor key the current `discovered` belongs to (empty while a new grain loads). */
  discoveredFor: string

  result: GraphQueryResponse | null
  running: boolean
  error: string | null
  rowsLoadingMore: boolean

  /** Flattened convenience: the current list spec (null in aggregate mode). */
  listSpec: ListSpec | null
  runnable: boolean

  run: () => void
  loadMore: () => void
  refresh: () => void
  loadColumnFacets: (columnId: string, search: string) => Promise<FacetBucket[]>
  /** Discover the columns of an arbitrary class (for relation-expansion / 2-hop fields). */
  discoverColumnsFor: (classUri: string) => Promise<DiscoveredColumn[]>
}

/** All Explore data flow for one workspace: discovery, query execution, facets. */
export function useExplore(workspaceId: string): UseExplore {
  const [state, dispatch] = useReducer(exploreReducer, undefined, initialExploreState)

  const [graphs, setGraphs] = useState<GraphPack[]>([])
  const [graphsLoading, setGraphsLoading] = useState(false)
  const [classes, setClasses] = useState<ClassInfo[]>([])
  const [classesLoading, setClassesLoading] = useState(false)
  const [discovered, setDiscovered] = useState<DiscoveredColumn[]>([])
  const [discoveredLoading, setDiscoveredLoading] = useState(false)
  // The anchor key the current `discovered` belongs to (guards column auto-seed against
  // stale results while a new grain's discovery is in flight).
  const [discoveredFor, setDiscoveredFor] = useState('')

  const [result, setResult] = useState<GraphQueryResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [rowsLoadingMore, setRowsLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // A monotonically increasing token guards against out-of-order responses.
  const runToken = useRef(0)

  const spec = useMemo(() => specFromState(state), [state])
  const runnable = useMemo(() => isRunnable(spec), [spec])
  const specKey = useMemo(() => JSON.stringify(spec), [spec])
  const listSpec = spec.mode === 'list' ? spec : null

  // Graphs once per workspace.
  useEffect(() => {
    if (!workspaceId) return
    let cancelled = false
    setGraphsLoading(true)
    getJson<GraphPack[]>(`/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`)
      .then((data) => {
        if (!cancelled) setGraphs(data)
      })
      .catch(() => {
        if (!cancelled) setGraphs([])
      })
      .finally(() => {
        if (!cancelled) setGraphsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId])

  // Classes across ALL selected graphs (cross-graph views): discover per graph and merge by
  // class URI, summing instance counts so a class present in several graphs shows combined size.
  const graphsKey = state.graphUris.join('|')
  useEffect(() => {
    const graphUris = graphsKey ? graphsKey.split('|') : []
    if (!workspaceId || graphUris.length === 0) {
      setClasses([])
      return
    }
    let cancelled = false
    setClassesLoading(true)
    Promise.all(
      graphUris.map((g) =>
        getJson<ClassInfo[]>(
          `/api/graph/discovery/classes?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(g)}`,
        ).catch(() => [] as ClassInfo[]),
      ),
    )
      .then((lists) => {
        if (cancelled) return
        const byUri = new Map<string, ClassInfo>()
        for (const list of lists) {
          for (const c of list) {
            const existing = byUri.get(c.uri)
            if (existing) existing.count += c.count
            else byUri.set(c.uri, { ...c })
          }
        }
        setClasses([...byUri.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)))
      })
      .finally(() => {
        if (!cancelled) setClassesLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId, graphsKey])

  // Discover columns whenever the anchor (graphs × classes) changes.
  const anchorKey = `${state.graphUris.join('|')}::${state.classUris.join('|')}`
  useEffect(() => {
    if (!workspaceId || state.graphUris.length === 0 || state.classUris.length === 0) {
      setDiscovered([])
      setDiscoveredFor('')
      return
    }
    let cancelled = false
    // Clear immediately + retag so the column auto-seed never fires with the *previous*
    // grain's columns while the new grain's discovery is still in flight.
    setDiscovered([])
    setDiscoveredFor('')
    setDiscoveredLoading(true)
    fetchColumns({ workspaceId, graphUris: state.graphUris, classUris: state.classUris })
      .then((resp) => {
        if (!cancelled) {
          setDiscovered(resp.columns)
          setDiscoveredFor(anchorKey)
        }
      })
      .catch(() => {
        if (!cancelled) setDiscovered([])
      })
      .finally(() => {
        if (!cancelled) setDiscoveredLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, anchorKey])

  const execute = useCallback(
    async (mode: 'replace' | 'append') => {
      if (!runnable) {
        setResult(null)
        setError(null)
        return
      }
      const token = ++runToken.current
      if (mode === 'append') setRowsLoadingMore(true)
      else setRunning(true)
      setError(null)
      try {
        const cursor = mode === 'append' ? result?.page.next_cursor ?? null : null
        const resp = await runQuery(workspaceId, spec, { cursor, includeSparql: true })
        if (token !== runToken.current) return // superseded
        if (mode === 'append' && result) {
          // Keep the first page's resolved_sparql (the query shape is the same).
          setResult({ ...resp, rows: [...result.rows, ...resp.rows], resolved_sparql: result.resolved_sparql })
        } else {
          setResult(resp)
        }
      } catch (err) {
        if (token !== runToken.current) return
        const message = err instanceof GraphApiError ? err.detail : 'Query failed'
        setError(message)
        if (mode === 'replace') setResult(null)
      } finally {
        if (token === runToken.current) {
          setRunning(false)
          setRowsLoadingMore(false)
        }
      }
    },
    [runnable, result, spec, workspaceId],
  )

  const run = useCallback(() => void execute('replace'), [execute])
  const loadMore = useCallback(() => {
    if (result?.page.has_more) void execute('append')
  }, [execute, result])
  const refresh = run

  // Auto-run (debounced) whenever the spec changes and is runnable.
  useEffect(() => {
    if (!runnable) {
      setResult(null)
      return
    }
    const handle = setTimeout(() => void execute('replace'), AUTORUN_DEBOUNCE_MS)
    return () => clearTimeout(handle)
    // execute is intentionally excluded; specKey captures the meaningful change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specKey, runnable])

  const loadColumnFacets = useCallback(
    async (columnId: string, search: string): Promise<FacetBucket[]> => {
      if (!listSpec) return []
      const resp = await fetchFacets(workspaceId, listSpec, columnId, { search, limit: 50 })
      return resp.buckets
    },
    [listSpec, workspaceId],
  )

  const discoverColumnsFor = useCallback(
    async (classUri: string): Promise<DiscoveredColumn[]> => {
      if (!workspaceId || state.graphUris.length === 0 || !classUri) return []
      const resp = await fetchColumns({ workspaceId, graphUris: state.graphUris, classUris: [classUri] })
      return resp.columns
    },
    [workspaceId, state.graphUris],
  )

  return {
    state,
    dispatch,
    graphs,
    graphsLoading,
    classes,
    classesLoading,
    discovered,
    discoveredLoading,
    discoveredFor,
    result,
    running,
    error,
    rowsLoadingMore,
    listSpec,
    runnable,
    run,
    loadMore,
    refresh,
    loadColumnFacets,
    discoverColumnsFor,
  }
}

/** Map discovered columns → spec columns (re-exported for component use). */
export { discoveredToColumns }
