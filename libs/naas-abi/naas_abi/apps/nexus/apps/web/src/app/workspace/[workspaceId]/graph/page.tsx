'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Database,
  Download,
  FileUp,
  Filter,
  Info,
  LayoutList,
  Loader2,
  Pencil,
  RefreshCw,
  Save,
  Search,
  Share2,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import {
  useKnowledgeGraphStore,
  type DiscoveryViewState,
  type GraphEdge as StoreGraphEdge,
  type GraphNode as StoreGraphNode,
  type GraphView,
} from '@/stores/knowledge-graph';

const VisNetwork = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.VisNetwork),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center">
        <span className="text-muted-foreground">Loading graph...</span>
      </div>
    ),
  }
);

// ── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_PROPERTY_URIS = ['http://www.w3.org/2000/01/rdf-schema#label'];
const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';
const GRAPH_MAX_NODES = 20;
const GRAPH_MAX_EDGES = 20;
const DISCOVERY_DEBOUNCE_MS = 300;

// ── Backend types ────────────────────────────────────────────────────────────

interface ApiGraphInfo {
  id: string;
  uri: string;
  label: string;
  role_label: string;
}

interface ApiGraphPack {
  role_label: string;
  graphs: ApiGraphInfo[];
}

interface ApiDiscoveryClass {
  uri: string;
  label: string;
  count: number;
}

interface ApiDiscoveryProperty {
  uri: string;
  label: string;
  kind: string;
}

interface ApiDiscoveryInstance {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
  properties: Record<string, string>;
  domain_relations_count?: number;
  range_relations_count?: number;
  properties_count?: number;
}

interface ApiDiscoveryRelationType {
  uri: string;
  label: string;
  count: number;
}

interface ApiDiscoveryRelationRow {
  relation_uri: string;
  relation_label: string;
  domain_uri: string;
  domain_label: string;
  domain_class_uri: string;
  domain_class_label: string;
  range_uri: string;
  range_label: string;
  range_class_uri: string;
  range_class_label: string;
  role: 'domain' | 'range';
}

interface ApiDataPropertyItem {
  predicate_uri: string;
  predicate_label: string;
  value: string;
}

interface ApiInspectorRelation {
  role: 'domain' | 'range';
  predicate_uri: string;
  predicate_label: string;
  other_uri: string;
  other_label: string;
}

interface ApiInstanceDetail {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
  data_properties: ApiDataPropertyItem[];
  relations: ApiInspectorRelation[];
}

interface GraphImportAnalysis {
  total_triples: number;
  total_subjects: number;
  named_individuals_subjects: number;
  named_individuals_triples: number;
  classes_subjects: number;
  classes_triples: number;
  object_properties_subjects: number;
  object_properties_triples: number;
  datatype_properties_subjects: number;
  datatype_properties_triples: number;
  restrictions_subjects: number;
  restrictions_triples: number;
  unknown_subjects: number;
  unknown_triples: number;
}

type PageMode = 'discovery' | 'import';

interface ColumnFilter {
  search: string;
  excluded: Set<string>;
}

interface SortState {
  column: string;
  direction: 'asc' | 'desc';
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function compactUri(uri: string): string {
  if (!uri) return '';
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop();
      if (tail) return tail;
    }
  }
  return uri;
}

function isSystemGraph(graph: { id: string; label?: string }): boolean {
  const id = graph.id.trim().toLowerCase();
  const name = (graph.label ?? '').trim().toLowerCase();
  return (
    id === 'schema' ||
    id === 'nexus' ||
    id.endsWith('/schema') ||
    id.endsWith('/nexus') ||
    name === 'schema' ||
    name === 'nexus'
  );
}

function formatPropertyValue(value: string | undefined): string {
  if (value === undefined || value === null) return '';
  return String(value);
}

// ── Discovery Page ───────────────────────────────────────────────────────────

export default function GraphPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = params.workspaceId as string;

  const {
    selectedGraphId,
    visibleGraphIds,
    selectGraph,
    setVisibleGraphs,
    views,
    activeSavedViewId,
    setActiveSavedView,
    createSavedView,
    updateSavedView,
    deleteView,
  } = useKnowledgeGraphStore();

  // ── Mode ───────────────────────────────────────────────────────────────────

  const requestedMode = searchParams.get('view');
  const [pageMode, setPageMode] = useState<PageMode>(
    requestedMode === 'import' ? 'import' : 'discovery'
  );

  useEffect(() => {
    if (requestedMode === 'import') setPageMode('import');
    else setPageMode('discovery');
  }, [requestedMode]);

  // ── Graphs ─────────────────────────────────────────────────────────────────

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [graphsError, setGraphsError] = useState<string | null>(null);

  const allGraphs = useMemo<ApiGraphInfo[]>(() => {
    const seen = new Set<string>();
    const out: ApiGraphInfo[] = [];
    for (const pack of graphPacks) {
      for (const g of pack.graphs) {
        if (seen.has(g.uri)) continue;
        seen.add(g.uri);
        out.push(g);
      }
    }
    return out;
  }, [graphPacks]);

  const activeGraph = useMemo<ApiGraphInfo | null>(() => {
    if (selectedGraphId) {
      const match = allGraphs.find((g) => g.id === selectedGraphId);
      if (match) return match;
    }
    if (visibleGraphIds.length > 0) {
      const match = allGraphs.find((g) => visibleGraphIds.includes(g.id));
      if (match) return match;
    }
    return allGraphs.find((g) => !isSystemGraph(g)) ?? allGraphs[0] ?? null;
  }, [allGraphs, selectedGraphId, visibleGraphIds]);

  const loadGraphs = useCallback(async () => {
    setGraphsLoading(true);
    setGraphsError(null);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!res.ok) throw new Error(`Failed to load graphs (${res.status})`);
      const data = (await res.json()) as ApiGraphPack[];
      setGraphPacks(Array.isArray(data) ? data : []);
    } catch (err) {
      setGraphsError(err instanceof Error ? err.message : 'Failed to load graphs');
      setGraphPacks([]);
    } finally {
      setGraphsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadGraphs();
  }, [loadGraphs]);

  // ── Discovery state ────────────────────────────────────────────────────────

  const [classes, setClasses] = useState<ApiDiscoveryClass[]>([]);
  const [classesLoading, setClassesLoading] = useState(false);
  const [properties, setProperties] = useState<ApiDiscoveryProperty[]>([]);
  const [propertiesLoading, setPropertiesLoading] = useState(false);
  const [instances, setInstances] = useState<ApiDiscoveryInstance[]>([]);
  const [instancesLoading, setInstancesLoading] = useState(false);
  const [instancesError, setInstancesError] = useState<string | null>(null);
  const [relationsLoading, setRelationsLoading] = useState(false);
  const [relations, setRelations] = useState<ApiDiscoveryRelationRow[]>([]);
  const [relationsError, setRelationsError] = useState<string | null>(null);

  const [selectedClassUris, setSelectedClassUris] = useState<string[]>([]);
  const [selectedPropertyUris, setSelectedPropertyUris] =
    useState<string[]>(DEFAULT_PROPERTY_URIS);
  const [selectedRelationUris, setSelectedRelationUris] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  const [selectedInstanceUris, setSelectedInstanceUris] = useState<Set<string>>(new Set());
  const [highlightedNodeUri, setHighlightedNodeUri] = useState<string | null>(null);

  const [columnFilters, setColumnFilters] = useState<Record<string, ColumnFilter>>({});
  const [sortState, setSortState] = useState<SortState | null>(null);
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(new Set());

  const [relationColumnFilters, setRelationColumnFilters] = useState<
    Record<string, ColumnFilter>
  >({});
  const [relationSortState, setRelationSortState] = useState<SortState | null>(null);
  const [selectedRelationRowKeys, setSelectedRelationRowKeys] = useState<Set<string>>(
    new Set()
  );

  // ── Saved discovery views ──────────────────────────────────────────────────

  const discoveryViews = useMemo(
    () => views.filter((v) => v.type === 'entities' && v.discovery),
    [views]
  );

  const activeSavedView = useMemo(
    () =>
      activeSavedViewId
        ? discoveryViews.find((v) => v.id === activeSavedViewId) ?? null
        : null,
    [activeSavedViewId, discoveryViews]
  );

  const [savingView, setSavingView] = useState(false);
  const [showSaveViewDialog, setShowSaveViewDialog] = useState(false);
  const [saveViewName, setSaveViewName] = useState('');

  // Apply saved view to filters on selection
  const lastAppliedViewIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!activeSavedView || !activeSavedView.discovery) return;
    if (lastAppliedViewIdRef.current === activeSavedView.id) return;
    lastAppliedViewIdRef.current = activeSavedView.id;
    const d = activeSavedView.discovery;
    setSelectedClassUris(d.classUris);
    setSelectedPropertyUris(d.propertyUris.length ? d.propertyUris : DEFAULT_PROPERTY_URIS);
    setSelectedRelationUris(d.relationUris);
    setSearch(d.search);
    if (d.selectedInstanceUris?.length) {
      setSelectedInstanceUris(new Set(d.selectedInstanceUris));
    }
    if (d.selectedRelationRowKeys?.length) {
      setSelectedRelationRowKeys(new Set(d.selectedRelationRowKeys));
    }
  }, [activeSavedView]);

  // ── Debounce search ────────────────────────────────────────────────────────

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(search), DISCOVERY_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [search]);

  // ── Load classes when graph changes ────────────────────────────────────────

  const lastSeededGraphUriRef = useRef<string | null>(null);

  useEffect(() => {
    if (!activeGraph) {
      setClasses([]);
      return;
    }
    let cancelled = false;
    (async () => {
      setClassesLoading(true);
      try {
        const res = await authFetch(
          `${getApiUrl()}/api/graph/discovery/classes?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}`
        );
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = (await res.json()) as ApiDiscoveryClass[];
        if (!cancelled) {
          setClasses(data);
          // Auto-select all classes on first load for this graph; skip when a
          // saved view is active (it already specifies its own selection).
          if (
            !activeSavedView &&
            lastSeededGraphUriRef.current !== activeGraph.uri
          ) {
            lastSeededGraphUriRef.current = activeGraph.uri;
            setSelectedClassUris(data.map((c) => c.uri));
          }
        }
      } catch {
        if (!cancelled) setClasses([]);
      } finally {
        if (!cancelled) setClassesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeGraph, workspaceId]);

  // ── Load properties when classes change ────────────────────────────────────

  useEffect(() => {
    if (!activeGraph) {
      setProperties([]);
      return;
    }
    let cancelled = false;
    (async () => {
      setPropertiesLoading(true);
      try {
        const res = await authFetch(`${getApiUrl()}/api/graph/discovery/properties`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            class_uris: selectedClassUris,
          }),
        });
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = (await res.json()) as ApiDiscoveryProperty[];
        if (!cancelled) {
          setProperties(data);
          setSelectedPropertyUris((prev) =>
            prev.length === 0 ? DEFAULT_PROPERTY_URIS : prev
          );
        }
      } catch {
        if (!cancelled) setProperties([]);
      } finally {
        if (!cancelled) setPropertiesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeGraph, workspaceId, selectedClassUris]);

  // ── Load instances when filters/search change ──────────────────────────────

  useEffect(() => {
    if (!activeGraph || selectedPropertyUris.length === 0) {
      setInstances([]);
      setInstancesLoading(false);
      setInstancesError(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setInstancesLoading(true);
      setInstancesError(null);
      try {
        const res = await authFetch(`${getApiUrl()}/api/graph/discovery/instances`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            class_uris: selectedClassUris,
            property_uris: selectedPropertyUris,
            search: debouncedSearch,
          }),
        });
        if (!res.ok) throw new Error(`Search failed (${res.status})`);
        const data = (await res.json()) as ApiDiscoveryInstance[];
        if (!cancelled) {
          setInstances(data);
          setSelectedInstanceUris((prev) => {
            const next = new Set<string>();
            const valid = new Set(data.map((d) => d.uri));
            for (const uri of prev) if (valid.has(uri)) next.add(uri);
            return next;
          });
        }
      } catch (err) {
        if (!cancelled) {
          setInstancesError(err instanceof Error ? err.message : 'Search failed');
          setInstances([]);
        }
      } finally {
        if (!cancelled) setInstancesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    activeGraph,
    workspaceId,
    selectedClassUris,
    selectedPropertyUris,
    debouncedSearch,
  ]);

  // ── Working instance set: selected rows, else all visible (after column filters) ──

  const filteredInstances = useMemo(() => {
    let result = instances;
    for (const [colId, filter] of Object.entries(columnFilters)) {
      const search = filter.search.trim().toLowerCase();
      result = result.filter((inst) => {
        const value = getInstanceColumnValue(inst, colId);
        if (filter.excluded.has(value)) return false;
        if (search && !value.toLowerCase().includes(search)) return false;
        return true;
      });
    }
    if (sortState) {
      const dir = sortState.direction === 'asc' ? 1 : -1;
      const numericCols = new Set(['domain_relations', 'range_relations', 'properties']);
      const isNumeric = numericCols.has(sortState.column);
      result = [...result].sort((a, b) => {
        if (isNumeric) {
          const col = sortState.column;
          const av = col === 'domain_relations' ? (a.domain_relations_count ?? 0)
                   : col === 'range_relations'  ? (a.range_relations_count ?? 0)
                   : (a.properties_count ?? 0);
          const bv = col === 'domain_relations' ? (b.domain_relations_count ?? 0)
                   : col === 'range_relations'  ? (b.range_relations_count ?? 0)
                   : (b.properties_count ?? 0);
          if (av < bv) return -1 * dir;
          if (av > bv) return 1 * dir;
          return 0;
        }
        const av = getInstanceColumnValue(a, sortState.column).toLowerCase();
        const bv = getInstanceColumnValue(b, sortState.column).toLowerCase();
        if (av < bv) return -1 * dir;
        if (av > bv) return 1 * dir;
        return 0;
      });
    }
    return result;
  }, [instances, columnFilters, sortState]);

  const workingInstanceUris = useMemo(() => {
    if (selectedInstanceUris.size > 0) {
      return filteredInstances
        .filter((i) => selectedInstanceUris.has(i.uri))
        .map((i) => i.uri);
    }
    return filteredInstances.slice(0, GRAPH_MAX_NODES).map((i) => i.uri);
  }, [filteredInstances, selectedInstanceUris]);

  // Graph nodes come only from explicitly-selected instances (Table 1) —
  // range nodes from Table 2 relations are added on top of those.
  const graphInstanceUris = useMemo(
    () =>
      filteredInstances
        .filter((i) => selectedInstanceUris.has(i.uri))
        .map((i) => i.uri),
    [filteredInstances, selectedInstanceUris]
  );

  // Excel-like filtered + sorted relation rows (Table 2 view).
  const filteredRelations = useMemo(() => {
    let result = relations;
    for (const [colId, filter] of Object.entries(relationColumnFilters)) {
      const search = filter.search.trim().toLowerCase();
      result = result.filter((rel) => {
        const value = getRelationColumnValue(rel, colId);
        if (filter.excluded.has(value)) return false;
        if (search && !value.toLowerCase().includes(search)) return false;
        return true;
      });
    }
    if (relationSortState) {
      const dir = relationSortState.direction === 'asc' ? 1 : -1;
      result = [...result].sort((a, b) => {
        const av = getRelationColumnValue(a, relationSortState.column).toLowerCase();
        const bv = getRelationColumnValue(b, relationSortState.column).toLowerCase();
        if (av < bv) return -1 * dir;
        if (av > bv) return 1 * dir;
        return 0;
      });
    }
    return result;
  }, [relations, relationColumnFilters, relationSortState]);

  // ── Load relation types for working set ────────────────────────────────────

  const workingInstancesKey = workingInstanceUris.join('|');
  const selectedInstancesKey = useMemo(
    () => Array.from(selectedInstanceUris).sort().join('|'),
    [selectedInstanceUris]
  );
  const prevSelectedInstancesKeyRef = useRef<string>('');

  useEffect(() => {
    if (!activeGraph || workingInstanceUris.length === 0) {
      prevSelectedInstancesKeyRef.current = selectedInstancesKey;
      return;
    }
    const selectionChanged =
      selectedInstancesKey !== prevSelectedInstancesKeyRef.current;
    prevSelectedInstancesKeyRef.current = selectedInstancesKey;

    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch(`${getApiUrl()}/api/graph/discovery/relation-types`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            instance_uris: workingInstanceUris,
          }),
        });
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = (await res.json()) as ApiDiscoveryRelationType[];
        if (!cancelled) {
          setSelectedRelationUris((prev) => {
            if (data.length === 0) return [];
            // When the user just changed their explicit row selection, show
            // every relation for the new selection — don't try to preserve a
            // previous relation-type filter that would hide rows.
            if (selectionChanged && selectedInstanceUris.size > 0) {
              return data.map((d) => d.uri);
            }
            const valid = new Set(data.map((d) => d.uri));
            const kept = prev.filter((uri) => valid.has(uri));
            if (kept.length === 0) return data.map((d) => d.uri);
            return kept;
          });
        }
      } catch {
        // ignore — discovery is best-effort
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeGraph, workspaceId, workingInstancesKey, selectedInstancesKey]);

  // ── Load relations ─────────────────────────────────────────────────────────

  const selectedRelationKey = selectedRelationUris.join('|');

  useEffect(() => {
    if (
      !activeGraph ||
      instances.length === 0 ||
      workingInstanceUris.length === 0 ||
      selectedRelationUris.length === 0
    ) {
      setRelations([]);
      return;
    }
    let cancelled = false;
    (async () => {
      setRelationsLoading(true);
      setRelationsError(null);
      try {
        const res = await authFetch(`${getApiUrl()}/api/graph/discovery/relations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            instance_uris: workingInstanceUris,
            relation_uris: selectedRelationUris,
          }),
        });
        if (!res.ok) throw new Error(`Relations failed (${res.status})`);
        const data = (await res.json()) as ApiDiscoveryRelationRow[];
        if (!cancelled) {
          setRelations(data);
          // Drop any selected relation keys that no longer exist.
          setSelectedRelationRowKeys((prev) => {
            if (prev.size === 0) return prev;
            const validKeys = new Set(data.map(relationRowKey));
            const next = new Set<string>();
            for (const k of prev) if (validKeys.has(k)) next.add(k);
            return next;
          });
        }
      } catch (err) {
        if (!cancelled) {
          setRelationsError(err instanceof Error ? err.message : 'Relations failed');
          setRelations([]);
        }
      } finally {
        if (!cancelled) setRelationsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeGraph,
    workspaceId,
    workingInstancesKey,
    selectedRelationKey,
    instances.length,
  ]);

  // ── Build graph (capped at 20/20) ──────────────────────────────────────────

  const { graphNodes, graphEdges } = useMemo(() => {
    const nodesByUri = new Map<string, StoreGraphNode>();

    for (const uri of graphInstanceUris) {
      if (nodesByUri.size >= GRAPH_MAX_NODES) break;
      const inst = instances.find((i) => i.uri === uri);
      if (!inst) continue;
      nodesByUri.set(uri, {
        id: uri,
        label: inst.label || compactUri(inst.uri),
        type: inst.class_label || compactUri(inst.class_uri),
        properties: {
          ...inst.properties,
          class_uri: inst.class_uri,
        },
      });
    }

    const edges: StoreGraphEdge[] = [];
    const seenEdges = new Set<string>();
    // Network shows only what the user explicitly selected in the tables:
    // selected instances become source nodes, AND every selected relation row
    // adds its own domain + range nodes (even if the instance row itself isn't
    // ticked in Table 1) — so picking a row in Table 2 is enough to draw it.
    const relationsForGraph = filteredRelations.filter((r) =>
      selectedRelationRowKeys.has(relationRowKey(r))
    );
    for (const rel of relationsForGraph) {
      if (edges.length >= GRAPH_MAX_EDGES) break;
      // Add domain node if not already in the graph.
      if (!nodesByUri.has(rel.domain_uri) && nodesByUri.size < GRAPH_MAX_NODES) {
        nodesByUri.set(rel.domain_uri, {
          id: rel.domain_uri,
          label: rel.domain_label || compactUri(rel.domain_uri),
          type: rel.domain_class_label || compactUri(rel.domain_class_uri || ''),
          properties: { class_uri: rel.domain_class_uri },
        });
      }
      if (!nodesByUri.has(rel.domain_uri)) continue;
      // Add range node if not already in the graph.
      if (!nodesByUri.has(rel.range_uri) && nodesByUri.size < GRAPH_MAX_NODES) {
        nodesByUri.set(rel.range_uri, {
          id: rel.range_uri,
          label: rel.range_label || compactUri(rel.range_uri),
          type: rel.range_class_label || compactUri(rel.range_class_uri || ''),
          properties: { class_uri: rel.range_class_uri },
        });
      }
      if (!nodesByUri.has(rel.range_uri)) continue;
      const edgeKey = `${rel.domain_uri}|${rel.relation_uri}|${rel.range_uri}`;
      if (seenEdges.has(edgeKey)) continue;
      seenEdges.add(edgeKey);
      edges.push({
        id: edgeKey,
        source: rel.domain_uri,
        target: rel.range_uri,
        type: rel.relation_label || compactUri(rel.relation_uri),
        label: rel.relation_label || compactUri(rel.relation_uri),
      });
    }

    return { graphNodes: Array.from(nodesByUri.values()), graphEdges: edges };
  }, [
    instances,
    filteredRelations,
    graphInstanceUris,
    selectedRelationRowKeys,
  ]);

  // ── Handlers ───────────────────────────────────────────────────────────────

  const toggleClass = (uri: string) => {
    setSelectedClassUris((prev) =>
      prev.includes(uri) ? prev.filter((u) => u !== uri) : [...prev, uri]
    );
  };

  const toggleProperty = (uri: string) => {
    setSelectedPropertyUris((prev) =>
      prev.includes(uri) ? prev.filter((u) => u !== uri) : [...prev, uri]
    );
  };

  const toggleInstance = (uri: string) => {
    setSelectedInstanceUris((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) next.delete(uri);
      else next.add(uri);
      return next;
    });
  };

  const clearAllFilters = () => {
    setSelectedClassUris([]);
    setSelectedPropertyUris(DEFAULT_PROPERTY_URIS);
    setSelectedRelationUris([]);
    setSearch('');
    setSelectedInstanceUris(new Set());
    setColumnFilters({});
    setSortState(null);
    setHiddenColumns(new Set());
    setRelationColumnFilters({});
    setRelationSortState(null);
    setSelectedRelationRowKeys(new Set());
    setActiveSavedView(null);
    lastAppliedViewIdRef.current = null;
  };

  const handleSaveView = () => {
    const name = saveViewName.trim();
    if (!name) return;
    setSavingView(true);
    const discovery: DiscoveryViewState = {
      classUris: selectedClassUris,
      propertyUris: selectedPropertyUris,
      relationUris: selectedRelationUris,
      search: debouncedSearch,
      selectedInstanceUris: Array.from(selectedInstanceUris),
      selectedRelationRowKeys: Array.from(selectedRelationRowKeys),
    };
    const view = createSavedView(name, activeGraph ? [activeGraph.id] : [], []);
    updateSavedView(view.id, { discovery });
    setActiveSavedView(view.id);
    lastAppliedViewIdRef.current = view.id;
    setSavingView(false);
    setShowSaveViewDialog(false);
    setSaveViewName('');
  };

  const handleApplyView = (view: GraphView) => {
    setActiveSavedView(view.id);
  };

  const handleDeleteView = (view: GraphView) => {
    deleteView(view.id);
    if (activeSavedViewId === view.id) {
      setActiveSavedView(null);
      lastAppliedViewIdRef.current = null;
    }
  };

  const handleSelectNode = (nodeId: string | null) => {
    setHighlightedNodeUri(nodeId);
    if (nodeId) {
      const isInstance = instances.some((i) => i.uri === nodeId);
      if (isInstance) {
        setSelectedInstanceUris((prev) => {
          const next = new Set(prev);
          next.add(nodeId);
          return next;
        });
      }
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full flex-col">
      <Header />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Toolbar */}
          <div className="flex h-10 items-center justify-between border-b bg-muted/30 px-4">
            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  router.push(`/workspace/${workspaceId}/graph`);
                  setPageMode('discovery');
                }}
                className={cn(
                  'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                  pageMode === 'discovery'
                    ? 'bg-background'
                    : 'text-muted-foreground hover:bg-background'
                )}
              >
                <Search size={14} />
                Discovery
              </button>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setPageMode('import')}
                disabled={!activeGraph}
                className={cn(
                  'flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground',
                  !activeGraph && 'cursor-not-allowed opacity-50'
                )}
                title={
                  !activeGraph
                    ? 'Select a graph to import into'
                    : 'Import RDF file into graph'
                }
              >
                <Upload size={14} />
                Import
              </button>
              <ExportButton workspaceId={workspaceId} activeGraph={activeGraph} />
            </div>
          </div>

          {/* Body */}
          <div className="flex flex-1 overflow-hidden">
            {pageMode === 'import' ? (
              <ImportPane
                workspaceId={workspaceId}
                activeGraph={activeGraph}
                onClose={() => {
                  router.push(`/workspace/${workspaceId}/graph`);
                  setPageMode('discovery');
                }}
              />
            ) : graphsLoading ? (
              <div className="flex flex-1 items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : graphsError ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="max-w-md text-center">
                  <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
                  <p className="mb-2 text-sm">{graphsError}</p>
                  <button
                    onClick={() => void loadGraphs()}
                    className="mx-auto flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                  >
                    <RefreshCw size={14} />
                    Retry
                  </button>
                </div>
              </div>
            ) : !activeGraph ? (
              <div className="flex flex-1 items-center justify-center">
                <p className="text-sm text-muted-foreground">
                  No graphs available in this workspace.
                </p>
              </div>
            ) : (
              <DiscoveryPane
                graphs={allGraphs}
                activeGraph={activeGraph}
                graphsLoading={graphsLoading}
                onGraphChange={(g) => {
                  setActiveSavedView(null);
                  selectGraph(g.id);
                  setVisibleGraphs([g.id]);
                }}
                search={search}
                onSearchChange={setSearch}
                classes={classes}
                classesLoading={classesLoading}
                selectedClassUris={selectedClassUris}
                onToggleClass={toggleClass}
                onSetSelectedClasses={setSelectedClassUris}
                properties={properties}
                propertiesLoading={propertiesLoading}
                selectedPropertyUris={selectedPropertyUris}
                onToggleProperty={toggleProperty}
                onSetSelectedProperties={setSelectedPropertyUris}
                instances={instances}
                filteredInstances={filteredInstances}
                instancesLoading={instancesLoading}
                instancesError={instancesError}
                selectedInstanceUris={selectedInstanceUris}
                onToggleInstance={toggleInstance}
                onSetSelectedInstances={setSelectedInstanceUris}
                relations={relations}
                filteredRelations={filteredRelations}
                relationsLoading={relationsLoading}
                relationsError={relationsError}
                selectedRelationRowKeys={selectedRelationRowKeys}
                onToggleRelationRow={(key) =>
                  setSelectedRelationRowKeys((prev) => {
                    const next = new Set(prev);
                    if (next.has(key)) next.delete(key);
                    else next.add(key);
                    return next;
                  })
                }
                onSetSelectedRelationRows={setSelectedRelationRowKeys}
                relationColumnFilters={relationColumnFilters}
                onRelationColumnFiltersChange={setRelationColumnFilters}
                relationSortState={relationSortState}
                onRelationSortStateChange={setRelationSortState}
                graphNodes={graphNodes}
                graphEdges={graphEdges}
                highlightedNodeUri={highlightedNodeUri}
                onSelectNode={handleSelectNode}
                columnFilters={columnFilters}
                onColumnFiltersChange={setColumnFilters}
                sortState={sortState}
                onSortStateChange={setSortState}
                hiddenColumns={hiddenColumns}
                onHiddenColumnsChange={setHiddenColumns}
                onClearAll={clearAllFilters}
                savedViews={discoveryViews}
                activeSavedViewId={activeSavedViewId}
                onApplyView={handleApplyView}
                onDeleteView={handleDeleteView}
                onOpenSaveDialog={() => {
                  setSaveViewName(
                    activeSavedView?.name ??
                      `View ${new Date().toLocaleDateString()}`
                  );
                  setShowSaveViewDialog(true);
                }}
              />
            )}
          </div>
        </div>
      </div>

      {showSaveViewDialog && (
        <SaveViewDialog
          name={saveViewName}
          onNameChange={setSaveViewName}
          saving={savingView}
          onSave={handleSaveView}
          onCancel={() => {
            setShowSaveViewDialog(false);
            setSaveViewName('');
          }}
        />
      )}
    </div>
  );
}

// ── Graph filter ─────────────────────────────────────────────────────────────

function GraphFilter({
  graphs,
  activeGraph,
  loading,
  onChange,
}: {
  graphs: ApiGraphInfo[];
  activeGraph: ApiGraphInfo | null;
  loading: boolean;
  onChange: (graph: ApiGraphInfo) => void;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const filtered = useMemo(() => {
    const t = filter.trim().toLowerCase();
    if (!t) return graphs;
    return graphs.filter(
      (g) => g.label.toLowerCase().includes(t) || g.uri.toLowerCase().includes(t)
    );
  }, [graphs, filter]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="flex w-full items-center justify-between rounded-md border bg-background px-3 py-1.5 text-left text-sm hover:bg-muted/50"
      >
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Graph
          </span>
          <span className="truncate">
            {loading
              ? 'Loading...'
              : activeGraph?.label ?? 'Select graph'}
          </span>
        </div>
        <ChevronDown size={14} className="text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 max-h-72 w-full overflow-hidden rounded-md border bg-background shadow-lg">
          <div className="border-b p-2">
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter..."
              className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <p className="px-3 py-4 text-center text-xs text-muted-foreground">
                No graphs
              </p>
            ) : (
              filtered.map((g) => (
                <button
                  key={g.uri}
                  onClick={() => {
                    onChange(g);
                    setOpen(false);
                    setFilter('');
                  }}
                  className={cn(
                    'flex w-full items-center justify-between gap-2 px-3 py-1 text-left text-xs hover:bg-muted',
                    activeGraph?.uri === g.uri && 'bg-muted'
                  )}
                >
                  <span className="truncate" title={g.uri}>
                    {g.label}
                  </span>
                  {g.role_label && (
                    <span className="shrink-0 text-[10px] text-muted-foreground">
                      {g.role_label}
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Discovery pane ───────────────────────────────────────────────────────────

interface DiscoveryPaneProps {
  graphs: ApiGraphInfo[];
  activeGraph: ApiGraphInfo | null;
  graphsLoading: boolean;
  onGraphChange: (g: ApiGraphInfo) => void;
  search: string;
  onSearchChange: (s: string) => void;
  classes: ApiDiscoveryClass[];
  classesLoading: boolean;
  selectedClassUris: string[];
  onToggleClass: (uri: string) => void;
  onSetSelectedClasses: (uris: string[]) => void;
  properties: ApiDiscoveryProperty[];
  propertiesLoading: boolean;
  selectedPropertyUris: string[];
  onToggleProperty: (uri: string) => void;
  onSetSelectedProperties: (uris: string[]) => void;
  instances: ApiDiscoveryInstance[];
  filteredInstances: ApiDiscoveryInstance[];
  instancesLoading: boolean;
  instancesError: string | null;
  selectedInstanceUris: Set<string>;
  onToggleInstance: (uri: string) => void;
  onSetSelectedInstances: (uris: Set<string>) => void;
  relations: ApiDiscoveryRelationRow[];
  filteredRelations: ApiDiscoveryRelationRow[];
  relationsLoading: boolean;
  relationsError: string | null;
  selectedRelationRowKeys: Set<string>;
  onToggleRelationRow: (key: string) => void;
  onSetSelectedRelationRows: (keys: Set<string>) => void;
  relationColumnFilters: Record<string, ColumnFilter>;
  onRelationColumnFiltersChange: (
    updater:
      | Record<string, ColumnFilter>
      | ((prev: Record<string, ColumnFilter>) => Record<string, ColumnFilter>)
  ) => void;
  relationSortState: SortState | null;
  onRelationSortStateChange: (s: SortState | null) => void;
  graphNodes: StoreGraphNode[];
  graphEdges: StoreGraphEdge[];
  highlightedNodeUri: string | null;
  onSelectNode: (id: string | null) => void;
  columnFilters: Record<string, ColumnFilter>;
  onColumnFiltersChange: (
    updater:
      | Record<string, ColumnFilter>
      | ((prev: Record<string, ColumnFilter>) => Record<string, ColumnFilter>)
  ) => void;
  sortState: SortState | null;
  onSortStateChange: (s: SortState | null) => void;
  hiddenColumns: Set<string>;
  onHiddenColumnsChange: (
    updater: Set<string> | ((prev: Set<string>) => Set<string>)
  ) => void;
  onClearAll: () => void;
  savedViews: GraphView[];
  activeSavedViewId: string | null;
  onApplyView: (v: GraphView) => void;
  onDeleteView: (v: GraphView) => void;
  onOpenSaveDialog: () => void;
}

function DiscoveryPane(props: DiscoveryPaneProps) {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const {
    graphs,
    activeGraph,
    graphsLoading,
    onGraphChange,
    search,
    onSearchChange,
    classes,
    classesLoading,
    selectedClassUris,
    onToggleClass,
    onSetSelectedClasses,
    properties,
    propertiesLoading,
    selectedPropertyUris,
    onToggleProperty,
    onSetSelectedProperties,
    instances,
    filteredInstances,
    instancesLoading,
    instancesError,
    selectedInstanceUris,
    onToggleInstance,
    onSetSelectedInstances,
    relations,
    filteredRelations,
    relationsLoading,
    relationsError,
    selectedRelationRowKeys,
    onToggleRelationRow,
    onSetSelectedRelationRows,
    relationColumnFilters,
    onRelationColumnFiltersChange,
    relationSortState,
    onRelationSortStateChange,
    graphNodes,
    graphEdges,
    highlightedNodeUri,
    onSelectNode,
    columnFilters,
    onColumnFiltersChange,
    sortState,
    onSortStateChange,
    hiddenColumns,
    onHiddenColumnsChange,
    onClearAll,
    savedViews,
    activeSavedViewId,
    onApplyView,
    onDeleteView,
    onOpenSaveDialog,
  } = props;

  // Bump stabilizeKey whenever the visible graph composition changes so
  // vis-network re-runs physics and auto-fits to the canvas.
  const graphCompositionKey = useMemo(() => {
    const nodeIds = graphNodes.map((n) => n.id).sort().join('|');
    const edgeIds = graphEdges.map((e) => e.id).sort().join('|');
    return `${nodeIds}::${edgeIds}`;
  }, [graphNodes, graphEdges]);
  const [stabilizeKey, setStabilizeKey] = useState(0);
  const lastGraphCompositionRef = useRef<string>('');
  useEffect(() => {
    if (graphCompositionKey !== lastGraphCompositionRef.current) {
      lastGraphCompositionRef.current = graphCompositionKey;
      setStabilizeKey((k) => k + 1);
    }
  }, [graphCompositionKey]);

  const [openSections, setOpenSections] = useState<string[]>(['instances', 'relations']);
  const instancesCollapsed = !openSections.includes('instances');
  const relationsCollapsed = !openSections.includes('relations');
  const networkCollapsed = !openSections.includes('network');
  const previewCollapsed = !openSections.includes('preview');
  const toggleSection = (id: string) =>
    setOpenSections((prev) => {
      if (prev.includes(id)) return prev.filter((s) => s !== id);
      const next = [...prev, id];
      return next.length > 2 ? next.slice(next.length - 2) : next;
    });
  const [inspectedInstance, setInspectedInstance] = useState<ApiDiscoveryInstance | null>(null);

  const prevAppliedViewIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (activeSavedViewId && activeSavedViewId !== prevAppliedViewIdRef.current) {
      prevAppliedViewIdRef.current = activeSavedViewId;
      setOpenSections(['network', 'preview']);
    }
    if (!activeSavedViewId) {
      prevAppliedViewIdRef.current = null;
    }
  }, [activeSavedViewId]);

  const [instancePage, setInstancePage] = useState(0);
  const [instancePageSize, setInstancePageSize] = useState(20);
  const [relationPage, setRelationPage] = useState(0);
  const [relationPageSize, setRelationPageSize] = useState(20);

  useEffect(() => { setInstancePage(0); }, [filteredInstances]);
  useEffect(() => { setRelationPage(0); }, [filteredRelations]);

  const pagedInstances = useMemo(
    () => filteredInstances.slice(instancePage * instancePageSize, (instancePage + 1) * instancePageSize),
    [filteredInstances, instancePage, instancePageSize]
  );

  const pagedRelations = useMemo(
    () => filteredRelations.slice(relationPage * relationPageSize, (relationPage + 1) * relationPageSize),
    [filteredRelations, relationPage, relationPageSize]
  );

  const previewInstances = useMemo(
    () => filteredInstances.filter((i) => selectedInstanceUris.has(i.uri)),
    [filteredInstances, selectedInstanceUris]
  );

  const previewRelations = useMemo(
    () => filteredRelations.filter((r) => selectedRelationRowKeys.has(relationRowKey(r))),
    [filteredRelations, selectedRelationRowKeys]
  );

  const baseColumns = [
    { id: 'uri', label: 'uri' },
    { id: RDFS_LABEL, label: 'rdfs:label' },
    { id: 'class', label: 'class' },
    { id: 'domain_relations', label: '→' },
    { id: 'range_relations', label: '←' },
    { id: 'properties', label: 'properties' },
  ];

  const propertyColumns = selectedPropertyUris
    .filter((uri) => uri !== RDFS_LABEL)
    .map((uri) => ({
      id: uri,
      label: properties.find((p) => p.uri === uri)?.label ?? compactUri(uri),
    }));

  const allColumns = [...baseColumns, ...propertyColumns];
  const visibleColumns = allColumns.filter((c) => !hiddenColumns.has(c.id));

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Top: search + filters */}
      <div className="border-b bg-card">
        <div className="flex items-center gap-3 border-b px-4 py-2">
          <div className="flex flex-1 items-center gap-2 rounded-md border bg-background px-3 py-1.5">
            <Search size={14} className="text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search instances by selected properties..."
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            {search && (
              <button onClick={() => onSearchChange('')}>
                <X size={14} className="text-muted-foreground hover:text-foreground" />
              </button>
            )}
          </div>
          {savedViews.length > 0 && (
            <SavedViewsMenu
              views={savedViews}
              activeSavedViewId={activeSavedViewId}
              onApply={onApplyView}
              onDelete={onDeleteView}
            />
          )}
          <button
            onClick={onOpenSaveDialog}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
            title="Save current filters as a view"
          >
            <Save size={14} />
            Save view
          </button>
          <button
            onClick={onClearAll}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted"
            title="Clear all filters"
          >
            <X size={14} />
            Clear
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3 px-4 py-2">
          <GraphFilter
            graphs={graphs}
            activeGraph={activeGraph}
            loading={graphsLoading}
            onChange={onGraphChange}
          />
          <CheckboxFilter
            label="Classes"
            loading={classesLoading}
            options={classes.map((c) => ({
              uri: c.uri,
              label: c.label,
              hint: `${c.count}`,
            }))}
            selected={selectedClassUris}
            onToggle={onToggleClass}
            onSetSelected={onSetSelectedClasses}
            emptyMessage="No classes in this graph."
          />
          <CheckboxFilter
            label="Properties"
            loading={propertiesLoading}
            options={properties.map((p) => ({
              uri: p.uri,
              label: p.label || compactUri(p.uri),
              hint: p.kind,
            }))}
            selected={selectedPropertyUris}
            onToggle={onToggleProperty}
            onSetSelected={onSetSelectedProperties}
            minSelected={1}
            minSelectedWarning="Select at least one property for search to work."
            emptyMessage="No properties found."
          />
        </div>
      </div>

      {/* Main body: tables column + optional inspector panel */}
      <div className="flex flex-1 overflow-hidden">
      {/* Left: Instances → Relations → Network */}
      <div className="flex flex-1 flex-col overflow-hidden">
          {/* Table 1: Instances */}
          <section
            className={cn(
              'flex flex-col overflow-hidden',
              instancesCollapsed || (!instancesLoading && pagedInstances.length > 0 && pagedInstances.length < instancePageSize)
                ? 'shrink-0'
                : 'min-h-[35%] flex-1'
            )}
          >
            <header className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
              <button
                type="button"
                onClick={() => toggleSection('instances')}
                className="flex items-center gap-2 text-left hover:text-workspace-accent"
                title={instancesCollapsed ? 'Expand' : 'Collapse'}
              >
                {instancesCollapsed ? (
                  <ChevronRight size={14} className="text-muted-foreground" />
                ) : (
                  <ChevronDown size={14} className="text-muted-foreground" />
                )}
                <Database size={14} className="text-muted-foreground" />
                <h3 className="text-sm font-semibold">Individuals</h3>
              </button>
              {!instancesCollapsed && (
                <ColumnVisibilityMenu
                  columns={allColumns}
                  hidden={hiddenColumns}
                  onChange={onHiddenColumnsChange}
                />
              )}
            </header>
            {!instancesCollapsed && (
            <>
            <div className="flex-1 overflow-auto">
              {selectedPropertyUris.length === 0 ? (
                <EmptyState
                  icon={AlertCircle}
                  text="Select at least one property for search to work."
                />
              ) : instancesError ? (
                <EmptyState icon={AlertCircle} text={instancesError} />
              ) : instancesLoading ? (
                <EmptyState icon={Loader2} text="Searching..." spinning />
              ) : instances.length === 0 ? (
                <EmptyState
                  icon={Search}
                  text="No matching individuals. Try selecting fewer classes or clear the search."
                />
              ) : (
                <InstancesTable
                  columns={visibleColumns}
                  rows={pagedInstances}
                  selectedUris={selectedInstanceUris}
                  inspectedUri={inspectedInstance?.uri ?? null}
                  onToggle={onToggleInstance}
                  onSetSelected={onSetSelectedInstances}
                  onRowClick={(uri) => {
                    const inst = filteredInstances.find((i) => i.uri === uri) ?? null;
                    setInspectedInstance(inst);
                  }}
                  columnFilters={columnFilters}
                  onColumnFiltersChange={onColumnFiltersChange}
                  sortState={sortState}
                  onSortStateChange={onSortStateChange}
                  instances={instances}
                />
              )}
            </div>
            {filteredInstances.length > 0 && (
              <TablePagination
                page={instancePage}
                pageSize={instancePageSize}
                total={filteredInstances.length}
                onPageChange={setInstancePage}
                onPageSizeChange={(s) => { setInstancePageSize(s); setInstancePage(0); }}
              />
            )}
            </>
            )}
          </section>

          {/* Table 2: Relations */}
          <section
            className={cn(
              'flex flex-col overflow-hidden border-t',
              relationsCollapsed || (!relationsLoading && pagedRelations.length > 0 && pagedRelations.length < relationPageSize)
                ? 'shrink-0'
                : 'min-h-[35%] flex-1'
            )}
          >
            <header className="flex items-center gap-2 border-b bg-muted/40 px-4 py-2">
              <button
                type="button"
                onClick={() => toggleSection('relations')}
                className="flex items-center gap-2 text-left hover:text-workspace-accent"
                title={relationsCollapsed ? 'Expand' : 'Collapse'}
              >
                {relationsCollapsed ? (
                  <ChevronRight size={14} className="text-muted-foreground" />
                ) : (
                  <ChevronDown size={14} className="text-muted-foreground" />
                )}
                <ArrowRight size={14} className="text-muted-foreground" />
                <h3 className="text-sm font-semibold">Relations</h3>
              </button>
            </header>
            {!relationsCollapsed && (
            <>
            <div className="flex-1 overflow-auto">
              {relationsError ? (
                <EmptyState icon={AlertCircle} text={relationsError} />
              ) : relationsLoading ? (
                <EmptyState icon={Loader2} text="Loading..." spinning />
              ) : instances.length === 0 ? (
                <EmptyState icon={ArrowRight} text="Run a search in the Individuals table to see relations." />
              ) : relations.length === 0 ? (
                <EmptyState icon={ArrowRight} text="No relations for the current selection." />
              ) : (
                <RelationsTable
                  rows={pagedRelations}
                  allRows={relations}
                  selectedRowKeys={selectedRelationRowKeys}
                  onToggleRow={onToggleRelationRow}
                  onSetSelectedRows={onSetSelectedRelationRows}
                  onSelectNode={onSelectNode}
                  onInspectInstance={setInspectedInstance}
                  columnFilters={relationColumnFilters}
                  onColumnFiltersChange={onRelationColumnFiltersChange}
                  sortState={relationSortState}
                  onSortStateChange={onRelationSortStateChange}
                />
              )}
            </div>
            {filteredRelations.length > 0 && (
              <TablePagination
                page={relationPage}
                pageSize={relationPageSize}
                total={filteredRelations.length}
                onPageChange={setRelationPage}
                onPageSizeChange={(s) => { setRelationPageSize(s); setRelationPage(0); }}
              />
            )}
            </>
            )}
          </section>

        {/* Table 3: Network */}
        <section
          className={cn(
            'flex flex-col overflow-hidden border-t',
            networkCollapsed
              ? 'shrink-0'
              : 'min-h-[300px] flex-1'
          )}
        >
          <header className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
            <button
              type="button"
              onClick={() => toggleSection('network')}
              className="flex items-center gap-2 text-left hover:text-workspace-accent"
              title={networkCollapsed ? 'Expand' : 'Collapse'}
            >
              {networkCollapsed ? (
                <ChevronRight size={14} className="text-muted-foreground" />
              ) : (
                <ChevronDown size={14} className="text-muted-foreground" />
              )}
              <Share2 size={14} className="text-muted-foreground" />
              <h3 className="text-sm font-semibold">Network preview</h3>
            </button>
            {!networkCollapsed && (
              <span className="text-xs text-muted-foreground">
                {graphNodes.length} / {GRAPH_MAX_NODES} nodes ·{' '}
                {graphEdges.length} / {GRAPH_MAX_EDGES} edges
              </span>
            )}
          </header>
          {!networkCollapsed && (
            <div className="flex-1">
              {graphNodes.length === 0 ? (
                <EmptyState
                  icon={Filter}
                  text="Select rows in the Individuals and Relations tables to populate the network."
                />
              ) : (
                <VisNetwork
                  nodes={graphNodes}
                  edges={graphEdges}
                  selectedNodeId={highlightedNodeUri}
                  onNodeSelect={onSelectNode}
                  onEdgeSelect={() => {}}
                  physicsEnabled={true}
                  stabilizeKey={stabilizeKey}
                />
              )}
            </div>
          )}
        </section>

        {/* Table 4: Preview */}
        <section
          className={cn(
            'flex flex-col overflow-hidden border-t',
            previewCollapsed || (!previewCollapsed && previewInstances.length + previewRelations.length === 0)
              ? 'shrink-0'
              : 'min-h-[35%] flex-1'
          )}
        >
          <header className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
            <button
              type="button"
              onClick={() => toggleSection('preview')}
              className="flex items-center gap-2 text-left hover:text-workspace-accent"
              title={previewCollapsed ? 'Expand' : 'Collapse'}
            >
              {previewCollapsed ? (
                <ChevronRight size={14} className="text-muted-foreground" />
              ) : (
                <ChevronDown size={14} className="text-muted-foreground" />
              )}
              <LayoutList size={14} className="text-muted-foreground" />
              <h3 className="text-sm font-semibold">Table preview</h3>
            </button>
            {!previewCollapsed && (previewInstances.length > 0 || previewRelations.length > 0) && (
              <PreviewExportMenu instances={previewInstances} relations={previewRelations} />
            )}
          </header>
          {!previewCollapsed && (
            <div className="flex-1 overflow-auto">
              <PreviewTable instances={previewInstances} relations={previewRelations} />
            </div>
          )}
        </section>
      </div>

      {/* Right: Inspector panel */}
      {inspectedInstance && (
        <InstanceInspector
          instance={inspectedInstance}
          graphUri={activeGraph?.uri ?? ''}
          workspaceId={workspaceId}
          onClose={() => setInspectedInstance(null)}
        />
      )}
      </div>
    </div>
  );
}

// ── Preview table + export ────────────────────────────────────────────────────

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function PreviewExportMenu({
  instances,
  relations,
}: {
  instances: ApiDiscoveryInstance[];
  relations: ApiDiscoveryRelationRow[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const handleJSON = () => {
    const data = {
      instances: instances.map((i) => ({
        uri: i.uri,
        label: i.label,
        class_uri: i.class_uri,
        class_label: i.class_label,
      })),
      relations: relations.map((r) => ({
        domain_uri: r.domain_uri,
        domain_label: r.domain_label,
        relation_uri: r.relation_uri,
        relation_label: r.relation_label,
        range_uri: r.range_uri,
        range_label: r.range_label,
      })),
    };
    downloadBlob(JSON.stringify(data, null, 2), 'preview.json', 'application/json');
    setOpen(false);
  };

  const handleCSV = () => {
    const csvCell = (v: string) => `"${(v ?? '').replace(/"/g, '""')}"`;
    const rows: string[] = [];
    if (instances.length > 0) {
      rows.push('# Instances');
      rows.push('uri,label,class_uri,class_label');
      for (const i of instances)
        rows.push([i.uri, i.label, i.class_uri, i.class_label].map(csvCell).join(','));
    }
    if (relations.length > 0) {
      if (rows.length > 0) rows.push('');
      rows.push('# Relations');
      rows.push('domain_uri,domain_label,relation_uri,relation_label,range_uri,range_label');
      for (const r of relations)
        rows.push(
          [r.domain_uri, r.domain_label, r.relation_uri, r.relation_label, r.range_uri, r.range_label]
            .map(csvCell)
            .join(',')
        );
    }
    downloadBlob(rows.join('\n'), 'preview.csv', 'text/csv');
    setOpen(false);
  };

  const handleTTL = () => {
    const esc = (s: string) => s.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    const lines = [
      '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .',
      '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
      '@prefix owl: <http://www.w3.org/2002/07/owl#> .',
      '',
    ];
    for (const i of instances) {
      const classTriple = i.class_uri ? `, <${i.class_uri}>` : '';
      lines.push(`<${i.uri}> a owl:NamedIndividual${classTriple} ;`);
      lines.push(`    rdfs:label "${esc(i.label)}" .`);
      lines.push('');
    }
    for (const r of relations)
      lines.push(`<${r.domain_uri}> <${r.relation_uri}> <${r.range_uri}> .`);
    downloadBlob(lines.join('\n'), 'preview.ttl', 'text/turtle');
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs hover:bg-muted"
        title="Export preview"
      >
        <Download size={12} />
        Export
        <ChevronDown size={11} />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-36 rounded-md border bg-background py-1 shadow-lg">
          <button onClick={handleJSON} className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted">JSON</button>
          <button onClick={handleCSV} className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted">CSV</button>
          <button onClick={handleTTL} className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted">Turtle (.ttl)</button>
        </div>
      )}
    </div>
  );
}

function PreviewTable({
  instances,
  relations,
}: {
  instances: ApiDiscoveryInstance[];
  relations: ApiDiscoveryRelationRow[];
}) {
  if (instances.length === 0 && relations.length === 0) {
    return (
      <EmptyState
        icon={LayoutList}
        text="Check individuals or relations to populate the preview."
      />
    );
  }

  return (
    <div>
      {instances.length > 0 && (
        <>
          <div className="border-b bg-muted/60 px-4 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Individuals · {instances.length}
          </div>
          <table className="w-full text-xs">
            <thead className="sticky top-0 z-10 bg-muted">
              <tr>
                <th className="border-b px-3 py-1.5 text-left font-medium">URI</th>
                <th className="border-b px-3 py-1.5 text-left font-medium">Label</th>
                <th className="border-b px-3 py-1.5 text-left font-medium">Class</th>
              </tr>
            </thead>
            <tbody>
              {instances.map((inst) => (
                <tr key={inst.uri} className="border-b hover:bg-muted/50">
                  <td className="max-w-[260px] truncate px-3 py-1.5 font-mono text-[11px]" title={inst.uri}>{inst.uri}</td>
                  <td className="max-w-[200px] truncate px-3 py-1.5" title={inst.label}>{inst.label}</td>
                  <td className="max-w-[200px] truncate px-3 py-1.5" title={inst.class_uri}>{inst.class_label || compactUri(inst.class_uri)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {relations.length > 0 && (
        <>
          <div className={cn('border-b bg-muted/60 px-4 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground', instances.length > 0 && 'border-t')}>
            Relations · {relations.length}
          </div>
          <table className="w-full text-xs">
            <thead className="sticky top-0 z-10 bg-muted">
              <tr>
                <th className="border-b px-3 py-1.5 text-left font-medium">Domain</th>
                <th className="border-b px-3 py-1.5 text-left font-medium">Relation</th>
                <th className="border-b px-3 py-1.5 text-left font-medium">Range</th>
              </tr>
            </thead>
            <tbody>
              {relations.map((r) => (
                <tr key={relationRowKey(r)} className="border-b hover:bg-muted/50">
                  <td className="max-w-[200px] truncate px-3 py-1.5" title={r.domain_uri}>{r.domain_label || compactUri(r.domain_uri)}</td>
                  <td className="max-w-[200px] truncate px-3 py-1.5 font-medium" title={r.relation_uri}>{r.relation_label || compactUri(r.relation_uri)}</td>
                  <td className="max-w-[200px] truncate px-3 py-1.5" title={r.range_uri}>{r.range_label || compactUri(r.range_uri)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

// ── Instance inspector ────────────────────────────────────────────────────────

function InstanceInspector({
  instance,
  graphUri,
  workspaceId,
  onClose,
}: {
  instance: ApiDiscoveryInstance;
  graphUri: string;
  workspaceId: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<ApiInstanceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [relationsCollapsed, setRelationsCollapsed] = useState(false);
  const [roleFilter, setRoleFilter] = useState<'domain' | 'range'>('domain');

  useEffect(() => {
    if (!graphUri || !instance.uri) return;
    setDetail(null);
    setLoading(true);
    void authFetch(`${getApiUrl()}/api/graph/discovery/instance-detail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        graph_uri: graphUri,
        instance_uri: instance.uri,
      }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setDetail(data as ApiInstanceDetail))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [instance.uri, graphUri, workspaceId]);

  const filteredRelations = useMemo(
    () => (detail?.relations ?? []).filter((r) => r.role === roleFilter),
    [detail, roleFilter]
  );

  return (
    <aside className="flex min-w-[45%] w-[45%] flex-col overflow-hidden border-l bg-card">
      {/* Header */}
      <header className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
        <div className="flex items-center gap-2">
          <Info size={14} className="text-muted-foreground" />
          <h3 className="text-sm font-semibold">Inspector</h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground"
          title="Close inspector"
        >
          <X size={14} />
        </button>
      </header>

      <div className="flex-1 overflow-auto px-4 py-3 space-y-4 text-xs">
        {/* URI */}
        <div>
          <div className="mb-0.5 font-medium text-muted-foreground uppercase tracking-wide text-[10px]">URI</div>
          <span className="font-mono break-all text-[11px]">{instance.uri}</span>
        </div>

        {/* Label */}
        <div>
          <div className="mb-0.5 font-medium text-muted-foreground uppercase tracking-wide text-[10px]">Label</div>
          <span>{instance.label || '—'}</span>
        </div>

        {/* Class */}
        <div>
          <div className="mb-0.5 font-medium text-muted-foreground uppercase tracking-wide text-[10px]">Class</div>
          <div>{instance.class_label || compactUri(instance.class_uri)}</div>
          <div className="font-mono text-[11px] text-muted-foreground break-all">{instance.class_uri}</div>
        </div>

        {/* Data properties */}
        <div>
          <div className="mb-1 font-medium text-muted-foreground uppercase tracking-wide text-[10px]">
            Data properties
          </div>
          {loading ? (
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Loader2 size={12} className="animate-spin" />
              Loading…
            </div>
          ) : detail && detail.data_properties.length > 0 ? (
            <div className="space-y-2">
              {detail.data_properties.map((dp, i) => (
                <div key={`${dp.predicate_uri}-${i}`}>
                  <div className="text-muted-foreground">{dp.predicate_label}</div>
                  <div className="break-all">{dp.value}</div>
                </div>
              ))}
            </div>
          ) : detail ? (
            <div className="text-muted-foreground">No data properties.</div>
          ) : null}
        </div>

        {/* Relations */}
        <div className="border-t pt-3">
          <button
            type="button"
            onClick={() => setRelationsCollapsed((v) => !v)}
            className="flex items-center gap-1.5 font-medium text-muted-foreground uppercase tracking-wide text-[10px] hover:text-foreground w-full"
          >
            {relationsCollapsed ? (
              <ChevronRight size={12} />
            ) : (
              <ChevronDown size={12} />
            )}
            Relations
            {detail && (
              <span className="ml-auto normal-case tracking-normal font-normal">
                {detail.relations.length}
              </span>
            )}
          </button>

          {!relationsCollapsed && (
            <div className="mt-2 space-y-3">
              {/* Role toggle */}
              <div className="flex gap-1">
                {(['domain', 'range'] as const).map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => setRoleFilter(role)}
                    className={cn(
                      'rounded px-2 py-0.5 text-[11px] capitalize',
                      roleFilter === role
                        ? 'bg-workspace-accent text-white'
                        : 'bg-muted text-muted-foreground hover:bg-muted/70'
                    )}
                  >
                    {role}
                  </button>
                ))}
              </div>

              {loading ? (
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <Loader2 size={12} className="animate-spin" />
                  Loading…
                </div>
              ) : filteredRelations.length === 0 ? (
                <div className="text-muted-foreground">No {roleFilter} relations.</div>
              ) : (
                <div className="space-y-3">
                  {filteredRelations.map((r, i) => (
                    <div key={`${r.predicate_uri}-${r.other_uri}-${i}`} className="space-y-0.5">
                      <div className="text-muted-foreground">{r.predicate_label}</div>
                      <div>{r.other_label}</div>
                      <div className="font-mono text-[11px] text-muted-foreground break-all">{r.other_uri}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer actions */}
      <footer className="flex shrink-0 items-center gap-2 border-t bg-muted/20 px-4 py-2">
        <button
          type="button"
          disabled
          className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs opacity-50 cursor-not-allowed"
        >
          <Pencil size={12} />
          Edit
        </button>
        <button
          type="button"
          disabled
          className="flex items-center gap-1.5 rounded-md border border-red-300 px-3 py-1.5 text-xs text-red-500 opacity-50 cursor-not-allowed"
        >
          <Trash2 size={12} />
          Remove
        </button>
      </footer>
    </aside>
  );
}

// ── Tables ───────────────────────────────────────────────────────────────────

function getInstanceColumnValue(
  inst: ApiDiscoveryInstance,
  columnId: string
): string {
  if (columnId === 'uri') return inst.uri;
  if (columnId === 'class') return inst.class_label || compactUri(inst.class_uri);
  if (columnId === RDFS_LABEL)
    return inst.label || inst.properties[RDFS_LABEL] || compactUri(inst.uri);
  if (columnId === 'domain_relations') return String(inst.domain_relations_count ?? 0);
  if (columnId === 'range_relations') return String(inst.range_relations_count ?? 0);
  if (columnId === 'properties') return String(inst.properties_count ?? 0);
  return formatPropertyValue(inst.properties[columnId]);
}

interface InstancesTableProps {
  columns: { id: string; label: string }[];
  rows: ApiDiscoveryInstance[];
  instances: ApiDiscoveryInstance[];
  selectedUris: Set<string>;
  inspectedUri: string | null;
  onToggle: (uri: string) => void;
  onSetSelected: (uris: Set<string>) => void;
  onRowClick: (uri: string) => void;
  columnFilters: Record<string, ColumnFilter>;
  onColumnFiltersChange: (
    updater:
      | Record<string, ColumnFilter>
      | ((prev: Record<string, ColumnFilter>) => Record<string, ColumnFilter>)
  ) => void;
  sortState: SortState | null;
  onSortStateChange: (s: SortState | null) => void;
}

function InstancesTable({
  columns,
  rows,
  instances,
  selectedUris,
  inspectedUri,
  onToggle,
  onSetSelected,
  onRowClick,
  columnFilters,
  onColumnFiltersChange,
  sortState,
  onSortStateChange,
}: InstancesTableProps) {
  const selectAllRef = useRef<HTMLInputElement>(null);
  const visibleSelectedCount = rows.reduce(
    (acc, r) => (selectedUris.has(r.uri) ? acc + 1 : acc),
    0
  );
  const allVisibleSelected =
    rows.length > 0 && visibleSelectedCount === rows.length;
  const noneVisibleSelected = visibleSelectedCount === 0;
  const indeterminate = !allVisibleSelected && !noneVisibleSelected;

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  const handleToggleAll = () => {
    const visibleUris = new Set(rows.map((r) => r.uri));
    if (allVisibleSelected) {
      // Deselect all visible rows; keep selections outside the current filter.
      const next = new Set(selectedUris);
      for (const uri of visibleUris) next.delete(uri);
      onSetSelected(next);
    } else {
      // Select all visible rows on top of existing out-of-view selections.
      const next = new Set(selectedUris);
      for (const uri of visibleUris) next.add(uri);
      onSetSelected(next);
    }
  };

  const uniqueValuesByColumn = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const col of columns) {
      const set = new Set<string>();
      for (const inst of instances) set.add(getInstanceColumnValue(inst, col.id));
      out[col.id] = Array.from(set).sort();
    }
    return out;
  }, [instances, columns]);

  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 z-10 bg-muted">
        <tr>
          <th className="w-8 border-b px-2 py-1.5">
            <input
              ref={selectAllRef}
              type="checkbox"
              checked={allVisibleSelected}
              onChange={handleToggleAll}
              disabled={rows.length === 0}
              className="h-3.5 w-3.5"
              title={
                allVisibleSelected
                  ? 'Unselect all visible rows'
                  : 'Select all visible rows'
              }
            />
          </th>
          {columns.map((col) => (
            <ColumnHeader
              key={col.id}
              column={col}
              uniqueValues={uniqueValuesByColumn[col.id] ?? []}
              sortState={sortState}
              onSortStateChange={onSortStateChange}
              columnFilters={columnFilters}
              onColumnFiltersChange={onColumnFiltersChange}
            />
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && (
          <tr>
            <td
              colSpan={columns.length + 1}
              className="px-4 py-6 text-center text-xs text-muted-foreground"
            >
              No rows match the current filters.
            </td>
          </tr>
        )}
        {rows.map((inst) => {
          const isSelected = selectedUris.has(inst.uri);
          const isInspected = inspectedUri === inst.uri;
          return (
            <tr
              key={inst.uri}
              onClick={() => onRowClick(inst.uri)}
              className={cn(
                'cursor-pointer border-b hover:bg-muted/50',
                isSelected && 'bg-workspace-accent-10',
                isInspected && 'bg-workspace-accent-20'
              )}
            >
              <td className="px-2 py-1.5">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onClick={(e) => e.stopPropagation()}
                  onChange={() => onToggle(inst.uri)}
                  className="h-3.5 w-3.5"
                />
              </td>
              {columns.map((col) => {
                const value = getInstanceColumnValue(inst, col.id);
                return (
                  <td
                    key={col.id}
                    className="max-w-[260px] truncate px-3 py-1.5"
                    title={value}
                  >
                    {col.id === 'uri' ? (
                      <span className="font-mono text-[11px]">{value}</span>
                    ) : (
                      value
                    )}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ColumnHeader({
  column,
  uniqueValues,
  sortState,
  onSortStateChange,
  columnFilters,
  onColumnFiltersChange,
}: {
  column: { id: string; label: string };
  uniqueValues: string[];
  sortState: SortState | null;
  onSortStateChange: (s: SortState | null) => void;
  columnFilters: Record<string, ColumnFilter>;
  onColumnFiltersChange: (
    updater:
      | Record<string, ColumnFilter>
      | ((prev: Record<string, ColumnFilter>) => Record<string, ColumnFilter>)
  ) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLTableCellElement>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const filter = columnFilters[column.id] ?? {
    search: '',
    excluded: new Set<string>(),
  };

  const isSorted = sortState?.column === column.id;
  const sortDir = isSorted ? sortState!.direction : null;

  const updateFilter = (next: Partial<ColumnFilter>) => {
    onColumnFiltersChange((prev) => ({
      ...prev,
      [column.id]: {
        search: next.search ?? filter.search,
        excluded: next.excluded ?? filter.excluded,
      },
    }));
  };

  const toggleSort = () => {
    if (!isSorted) onSortStateChange({ column: column.id, direction: 'asc' });
    else if (sortDir === 'asc')
      onSortStateChange({ column: column.id, direction: 'desc' });
    else onSortStateChange(null);
  };

  const hasFilter = filter.search.length > 0 || filter.excluded.size > 0;

  const displayedValues = useMemo(() => {
    const t = filter.search.trim().toLowerCase();
    if (!t) return uniqueValues;
    return uniqueValues.filter((v) => v.toLowerCase().includes(t));
  }, [uniqueValues, filter.search]);

  const checkedCount = displayedValues.filter((v) => !filter.excluded.has(v)).length;
  const allChecked = displayedValues.length > 0 && checkedCount === displayedValues.length;
  const noneChecked = checkedCount === 0;
  const indeterminate = !allChecked && !noneChecked;

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  const handleSelectAll = () => {
    const next = new Set(filter.excluded);
    if (allChecked) {
      for (const v of displayedValues) next.add(v);
    } else {
      for (const v of displayedValues) next.delete(v);
    }
    updateFilter({ excluded: next });
  };

  return (
    <th
      ref={ref}
      className="relative border-b px-3 py-1.5 text-left text-xs font-medium"
    >
      <div className="flex items-center gap-1">
        <button
          onClick={toggleSort}
          className="flex items-center gap-1 hover:text-workspace-accent"
          title="Sort"
        >
          <span>{column.label}</span>
          {sortDir === 'asc' && <ChevronUp size={12} />}
          {sortDir === 'desc' && <ChevronDown size={12} />}
        </button>
        <button
          onClick={() => setOpen((p) => !p)}
          className={cn(
            'rounded p-0.5 hover:bg-muted-foreground/20',
            hasFilter && 'text-workspace-accent'
          )}
          title="Filter"
        >
          <Filter size={11} />
        </button>
      </div>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 w-64 overflow-hidden rounded-md border bg-background shadow-lg">
          <div className="border-b p-2">
            <input
              value={filter.search}
              onChange={(e) => updateFilter({ search: e.target.value })}
              placeholder="Filter..."
              className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          {displayedValues.length > 0 && (
            <label className="flex cursor-pointer items-center gap-2 border-b bg-muted/40 px-3 py-1.5 text-xs font-medium hover:bg-muted">
              <input
                ref={selectAllRef}
                type="checkbox"
                checked={allChecked && !noneChecked}
                onChange={handleSelectAll}
                className="h-3 w-3"
              />
              <span className="flex-1">Select all</span>
              <span className="text-[10px] text-muted-foreground">
                {checkedCount} / {displayedValues.length}
              </span>
            </label>
          )}
          <div className="max-h-48 overflow-y-auto py-1">
            {displayedValues.length === 0 ? (
              <p className="px-2 py-1 text-xs text-muted-foreground">No values</p>
            ) : (
              displayedValues.map((v) => {
                const checked = !filter.excluded.has(v);
                return (
                  <label
                    key={v}
                    className="flex cursor-pointer items-center gap-2 px-3 py-1 text-xs hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        const next = new Set(filter.excluded);
                        if (checked) next.add(v);
                        else next.delete(v);
                        updateFilter({ excluded: next });
                      }}
                      className="h-3 w-3"
                    />
                    <span className="flex-1 truncate" title={v}>
                      {v || <em className="text-muted-foreground">empty</em>}
                    </span>
                  </label>
                );
              })
            )}
          </div>
        </div>
      )}
    </th>
  );
}

const RELATION_COLUMNS: { id: string; label: string }[] = [
  { id: 'domain_uri', label: 'domain uri' },
  { id: 'domain', label: 'domain' },
  { id: 'relation', label: 'relation' },
  { id: 'range_uri', label: 'range uri' },
  { id: 'range', label: 'range' },
];

function getRelationColumnValue(
  row: ApiDiscoveryRelationRow,
  columnId: string
): string {
  switch (columnId) {
    case 'relation':
      return row.relation_label || compactUri(row.relation_uri);
    case 'domain_uri':
      return row.domain_uri;
    case 'domain':
      return row.domain_label;
    case 'range_uri':
      return row.range_uri;
    case 'range':
      return row.range_label;
    default:
      return '';
  }
}

function relationRowKey(row: ApiDiscoveryRelationRow): string {
  return `${row.role}|${row.domain_uri}|${row.relation_uri}|${row.range_uri}`;
}

interface RelationsTableProps {
  rows: ApiDiscoveryRelationRow[];
  allRows: ApiDiscoveryRelationRow[];
  selectedRowKeys: Set<string>;
  onToggleRow: (key: string) => void;
  onSetSelectedRows: (keys: Set<string>) => void;
  onSelectNode: (uri: string | null) => void;
  onInspectInstance: (inst: ApiDiscoveryInstance) => void;
  columnFilters: Record<string, ColumnFilter>;
  onColumnFiltersChange: (
    updater:
      | Record<string, ColumnFilter>
      | ((prev: Record<string, ColumnFilter>) => Record<string, ColumnFilter>)
  ) => void;
  sortState: SortState | null;
  onSortStateChange: (s: SortState | null) => void;
}

function RelationsTable({
  rows,
  allRows,
  selectedRowKeys,
  onToggleRow,
  onSetSelectedRows,
  onSelectNode,
  onInspectInstance,
  columnFilters,
  onColumnFiltersChange,
  sortState,
  onSortStateChange,
}: RelationsTableProps) {
  const selectAllRef = useRef<HTMLInputElement>(null);
  const visibleKeys = useMemo(() => rows.map(relationRowKey), [rows]);
  const visibleSelectedCount = visibleKeys.reduce(
    (acc, k) => (selectedRowKeys.has(k) ? acc + 1 : acc),
    0
  );
  const allVisibleSelected =
    rows.length > 0 && visibleSelectedCount === rows.length;
  const noneVisibleSelected = visibleSelectedCount === 0;
  const indeterminate = !allVisibleSelected && !noneVisibleSelected;

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  const handleToggleAll = () => {
    const visibleSet = new Set(visibleKeys);
    if (allVisibleSelected) {
      const next = new Set(selectedRowKeys);
      for (const k of visibleSet) next.delete(k);
      onSetSelectedRows(next);
    } else {
      const next = new Set(selectedRowKeys);
      for (const k of visibleSet) next.add(k);
      onSetSelectedRows(next);
    }
  };

  const uniqueValuesByColumn = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const col of RELATION_COLUMNS) {
      const set = new Set<string>();
      for (const r of allRows) set.add(getRelationColumnValue(r, col.id));
      out[col.id] = Array.from(set).sort();
    }
    return out;
  }, [allRows]);

  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 z-10 bg-muted">
        <tr>
          <th className="w-8 border-b px-2 py-1.5">
            <input
              ref={selectAllRef}
              type="checkbox"
              checked={allVisibleSelected}
              onChange={handleToggleAll}
              disabled={rows.length === 0}
              className="h-3.5 w-3.5"
              title={
                allVisibleSelected
                  ? 'Unselect all visible rows'
                  : 'Select all visible rows'
              }
            />
          </th>
          {RELATION_COLUMNS.map((col) => (
            <ColumnHeader
              key={col.id}
              column={col}
              uniqueValues={uniqueValuesByColumn[col.id] ?? []}
              sortState={sortState}
              onSortStateChange={onSortStateChange}
              columnFilters={columnFilters}
              onColumnFiltersChange={onColumnFiltersChange}
            />
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && (
          <tr>
            <td
              colSpan={RELATION_COLUMNS.length + 1}
              className="px-4 py-6 text-center text-xs text-muted-foreground"
            >
              No rows match the current filters.
            </td>
          </tr>
        )}
        {rows.map((r) => {
          const key = relationRowKey(r);
          const isSelected = selectedRowKeys.has(key);
          return (
            <tr
              key={key}
              className={cn(
                'cursor-pointer border-b hover:bg-muted/50',
                isSelected && 'bg-workspace-accent-10'
              )}
              onClick={() => onSelectNode(r.range_uri)}
            >
              <td className="px-2 py-1.5">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onClick={(e) => e.stopPropagation()}
                  onChange={() => onToggleRow(key)}
                  className="h-3.5 w-3.5"
                />
              </td>
              <td
                className="max-w-[260px] truncate px-3 py-1.5 font-mono text-[11px] hover:text-workspace-accent hover:underline"
                title={r.domain_uri}
                onClick={(e) => { e.stopPropagation(); onInspectInstance({ uri: r.domain_uri, label: r.domain_label, class_uri: r.domain_class_uri, class_label: r.domain_class_label, properties: {} }); }}
              >
                {r.domain_uri}
              </td>
              <td
                className="max-w-[200px] truncate px-3 py-1.5 hover:text-workspace-accent hover:underline"
                title={r.domain_label}
                onClick={(e) => { e.stopPropagation(); onInspectInstance({ uri: r.domain_uri, label: r.domain_label, class_uri: r.domain_class_uri, class_label: r.domain_class_label, properties: {} }); }}
              >
                {r.domain_label}
              </td>
              <td
                className="max-w-[200px] truncate px-3 py-1.5 font-medium"
                title={r.relation_uri}
              >
                {r.relation_label || compactUri(r.relation_uri)}
              </td>
              <td
                className="max-w-[260px] truncate px-3 py-1.5 font-mono text-[11px] hover:text-workspace-accent hover:underline"
                title={r.range_uri}
                onClick={(e) => { e.stopPropagation(); onInspectInstance({ uri: r.range_uri, label: r.range_label, class_uri: r.range_class_uri, class_label: r.range_class_label, properties: {} }); }}
              >
                {r.range_uri}
              </td>
              <td
                className="max-w-[200px] truncate px-3 py-1.5 hover:text-workspace-accent hover:underline"
                title={r.range_label}
                onClick={(e) => { e.stopPropagation(); onInspectInstance({ uri: r.range_uri, label: r.range_label, class_uri: r.range_class_uri, class_label: r.range_class_label, properties: {} }); }}
              >
                {r.range_label}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Column visibility menu ───────────────────────────────────────────────────

function ColumnVisibilityMenu({
  columns,
  hidden,
  onChange,
}: {
  columns: { id: string; label: string }[];
  hidden: Set<string>;
  onChange: (updater: Set<string> | ((prev: Set<string>) => Set<string>)) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-muted"
      >
        Columns
        <ChevronDown size={11} />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-48 rounded-md border bg-background py-1 shadow-lg">
          {columns.map((col) => {
            const isHidden = hidden.has(col.id);
            return (
              <label
                key={col.id}
                className="flex cursor-pointer items-center gap-2 px-3 py-1 text-xs hover:bg-muted"
              >
                <input
                  type="checkbox"
                  checked={!isHidden}
                  onChange={() => {
                    onChange((prev) => {
                      const next = new Set(prev);
                      if (isHidden) next.delete(col.id);
                      else next.add(col.id);
                      return next;
                    });
                  }}
                  className="h-3 w-3"
                />
                <span className="truncate">{col.label}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Table pagination ─────────────────────────────────────────────────────────

const PAGE_SIZE_OPTIONS = [20, 50, 100] as const;

function TablePagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (p: number) => void;
  onPageSizeChange: (size: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : page * pageSize + 1;
  const end = Math.min((page + 1) * pageSize, total);

  return (
    <div className="flex shrink-0 items-center justify-between border-t bg-muted/20 px-4 py-1.5 text-xs text-muted-foreground">
      <div className="flex items-center gap-2">
        <span>Rows per page:</span>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="rounded border bg-background px-1.5 py-0.5 text-xs outline-none focus:ring-1 focus:ring-primary"
        >
          {PAGE_SIZE_OPTIONS.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-1">
        <span className="mr-2">{start}–{end} of {total}</span>
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0}
          className="rounded p-0.5 hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
          title="Previous page"
        >
          <ChevronLeft size={14} />
        </button>
        <span className="min-w-[80px] text-center">
          Page {page + 1} of {totalPages}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages - 1}
          className="rounded p-0.5 hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
          title="Next page"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

// ── Checkbox filter ──────────────────────────────────────────────────────────

function CheckboxFilter({
  label,
  loading,
  options,
  selected,
  onToggle,
  onSetSelected,
  requiredUris,
  minSelected,
  minSelectedWarning,
  emptyMessage,
}: {
  label: string;
  loading: boolean;
  options: { uri: string; label: string; hint?: string }[];
  selected: string[];
  onToggle: (uri: string) => void;
  onSetSelected: (uris: string[]) => void;
  requiredUris?: string[];
  minSelected?: number;
  minSelectedWarning?: string;
  emptyMessage?: string;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const filtered = useMemo(() => {
    const t = filter.trim().toLowerCase();
    if (!t) return options;
    return options.filter(
      (o) => o.label.toLowerCase().includes(t) || o.uri.toLowerCase().includes(t)
    );
  }, [options, filter]);

  const required = useMemo(() => new Set(requiredUris ?? []), [requiredUris]);
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const visibleSelectedCount = filtered.reduce(
    (acc, o) => (selectedSet.has(o.uri) ? acc + 1 : acc),
    0
  );
  const allVisibleSelected =
    filtered.length > 0 && visibleSelectedCount === filtered.length;
  const noneVisibleSelected = visibleSelectedCount === 0;
  const indeterminate = !allVisibleSelected && !noneVisibleSelected;

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  const handleSelectAllToggle = () => {
    if (allVisibleSelected) {
      // Deselect all visible (keep required + non-visible selections)
      const visibleUris = new Set(filtered.map((o) => o.uri));
      const next = selected.filter(
        (uri) => !visibleUris.has(uri) || required.has(uri)
      );
      onSetSelected(next);
    } else {
      // Select all visible (merge with current selection)
      const next = new Set(selected);
      for (const o of filtered) next.add(o.uri);
      onSetSelected(Array.from(next));
    }
  };

  const summary =
    selected.length === 0
      ? 'None'
      : options.length > 0 && selected.length === options.length
        ? 'All'
        : selected.length === 1
          ? options.find((o) => o.uri === selected[0])?.label ?? compactUri(selected[0])
          : `${selected.length} selected`;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex w-full items-center justify-between rounded-md border bg-background px-3 py-1.5 text-left text-sm hover:bg-muted/50"
      >
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
          <span className="truncate">{loading ? 'Loading...' : summary}</span>
        </div>
        <ChevronDown size={14} className="text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 max-h-72 w-full overflow-hidden rounded-md border bg-background shadow-lg">
          <div className="border-b p-2">
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter..."
              className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          {filtered.length > 0 && (
            <label className="flex cursor-pointer items-center gap-2 border-b bg-muted/40 px-3 py-1.5 text-xs font-medium hover:bg-muted">
              <input
                ref={selectAllRef}
                type="checkbox"
                checked={allVisibleSelected}
                onChange={handleSelectAllToggle}
                className="h-3 w-3"
              />
              <span className="flex-1">Select all</span>
              <span className="text-[10px] text-muted-foreground">
                {visibleSelectedCount} / {filtered.length}
              </span>
            </label>
          )}
          {minSelected !== undefined &&
            selected.length < minSelected &&
            minSelectedWarning && (
              <div className="flex items-center gap-1.5 border-b bg-amber-50 px-3 py-1.5 text-xs text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
                <AlertCircle size={12} />
                {minSelectedWarning}
              </div>
            )}
          <div className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <p className="px-3 py-4 text-center text-xs text-muted-foreground">
                {emptyMessage ?? 'No options'}
              </p>
            ) : (
              filtered.map((opt) => {
                const isChecked = selectedSet.has(opt.uri);
                const isRequired = required.has(opt.uri);
                return (
                  <label
                    key={opt.uri}
                    className={cn(
                      'flex cursor-pointer items-center gap-2 px-3 py-1 text-xs hover:bg-muted',
                      isRequired && 'opacity-90'
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={isRequired}
                      onChange={() => onToggle(opt.uri)}
                      className="h-3 w-3"
                    />
                    <span className="flex-1 truncate" title={opt.uri}>
                      {opt.label}
                    </span>
                    {opt.hint && (
                      <span className="text-[10px] text-muted-foreground">
                        {opt.hint}
                      </span>
                    )}
                  </label>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Saved views menu ─────────────────────────────────────────────────────────

function SavedViewsMenu({
  views,
  activeSavedViewId,
  onApply,
  onDelete,
}: {
  views: GraphView[];
  activeSavedViewId: string | null;
  onApply: (v: GraphView) => void;
  onDelete: (v: GraphView) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
      >
        <Filter size={14} />
        Views ({views.length})
        <ChevronDown size={12} />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 w-72 rounded-md border bg-background shadow-lg">
          <div className="max-h-72 overflow-y-auto py-1">
            {views.map((v) => (
              <div
                key={v.id}
                className={cn(
                  'flex items-center justify-between gap-2 px-3 py-1.5 text-xs hover:bg-muted',
                  activeSavedViewId === v.id && 'bg-muted'
                )}
              >
                <button
                  className="flex-1 truncate text-left"
                  onClick={() => {
                    onApply(v);
                    setOpen(false);
                  }}
                >
                  {v.name}
                </button>
                <button
                  onClick={() => onDelete(v)}
                  className="text-muted-foreground hover:text-red-500"
                  title="Delete view"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Save view dialog ─────────────────────────────────────────────────────────

function SaveViewDialog({
  name,
  onNameChange,
  saving,
  onSave,
  onCancel,
}: {
  name: string;
  onNameChange: (s: string) => void;
  saving: boolean;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-96 rounded-lg border bg-background p-4 shadow-xl">
        <h3 className="mb-3 text-sm font-semibold">Save Discovery view</h3>
        <input
          autoFocus
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="View name"
          className="mb-3 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && name.trim()) onSave();
            if (e.key === 'Escape') onCancel();
          }}
        />
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            disabled={!name.trim() || saving}
            className="flex items-center gap-2 rounded-md bg-workspace-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({
  icon: Icon,
  text,
  spinning,
}: {
  icon: React.ElementType;
  text: string;
  spinning?: boolean;
}) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon size={16} className={cn(spinning && 'animate-spin')} />
        <span>{text}</span>
      </div>
    </div>
  );
}

// ── Import pane ──────────────────────────────────────────────────────────────

function ImportPane({
  workspaceId,
  activeGraph,
  onClose,
}: {
  workspaceId: string;
  activeGraph: ApiGraphInfo | null;
  onClose: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<GraphImportAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const analyze = async (f: File) => {
    setAnalyzing(true);
    setError(null);
    setAnalysis(null);
    try {
      const formData = new FormData();
      formData.append('workspace_id', workspaceId);
      formData.append('file', f);
      const response = await authFetch(`${getApiUrl()}/api/graph/analyze`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const detail = await response.text().catch(() => '');
        throw new Error(detail || `Analysis failed: ${response.status}`);
      }
      const data: GraphImportAnalysis = await response.json();
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleImport = async () => {
    if (!file || !activeGraph) return;
    setImporting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('workspace_id', workspaceId);
      formData.append('graph_uri', activeGraph.uri);
      formData.append('file', file);
      const response = await authFetch(`${getApiUrl()}/api/graph/import`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const text = await response.text().catch(() => '');
        throw new Error(text || `Import failed: ${response.status}`);
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col overflow-y-auto bg-card p-6">
      <div className="mx-auto w-full max-w-2xl">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FileUp size={24} className="text-workspace-accent" />
            <div>
              <h2 className="text-lg font-semibold">Import Graph</h2>
              <p className="text-sm text-muted-foreground">
                Target:{' '}
                <span className="font-medium text-foreground">
                  {activeGraph?.label ?? 'No graph selected'}
                </span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-2 text-muted-foreground hover:bg-muted"
            title="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-6">
          <div>
            <label className="mb-2 block text-sm font-medium">Select file</label>
            <div
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-lg border bg-background px-4 py-2.5 text-sm hover:bg-muted/50',
                file && 'border-workspace-accent/50'
              )}
              onClick={() => fileInputRef.current?.click()}
            >
              {analyzing ? (
                <Loader2 size={16} className="shrink-0 animate-spin text-muted-foreground" />
              ) : (
                <Upload size={16} className="shrink-0 text-muted-foreground" />
              )}
              <span
                className={cn(
                  'truncate',
                  file ? 'text-foreground' : 'text-muted-foreground'
                )}
              >
                {analyzing ? 'Analysing…' : file ? file.name : 'Choose a file…'}
              </span>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".ttl,.owl,.rdf,.nt,.n3,.jsonld"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setFile(f);
                setAnalysis(null);
                setError(null);
                if (f) void analyze(f);
              }}
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Supported: .ttl, .owl, .rdf, .nt, .n3
            </p>
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              {error}
            </div>
          )}

          {analysis && (
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="mb-3 flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-green-500" />
                  <p className="text-sm font-semibold">Analysis complete</p>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="pb-2 text-left text-xs font-medium text-muted-foreground" />
                      <th className="pb-2 text-right text-xs font-medium text-muted-foreground">
                        Subjects
                      </th>
                      <th className="pb-2 text-right text-xs font-medium text-muted-foreground">
                        Triples
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b font-medium">
                      <td className="py-2">Total</td>
                      <td className="py-2 text-right font-mono">
                        {analysis.total_subjects.toLocaleString()}
                      </td>
                      <td className="py-2 text-right font-mono">
                        {analysis.total_triples.toLocaleString()}
                      </td>
                    </tr>
                    {(
                      [
                        {
                          label: 'OWL Named Individuals',
                          s: analysis.named_individuals_subjects,
                          t: analysis.named_individuals_triples,
                          highlight: true,
                        },
                        {
                          label: 'OWL Classes',
                          s: analysis.classes_subjects,
                          t: analysis.classes_triples,
                          highlight: false,
                        },
                        {
                          label: 'Object Properties',
                          s: analysis.object_properties_subjects,
                          t: analysis.object_properties_triples,
                          highlight: false,
                        },
                        {
                          label: 'Datatype Properties',
                          s: analysis.datatype_properties_subjects,
                          t: analysis.datatype_properties_triples,
                          highlight: false,
                        },
                        {
                          label: 'Restrictions',
                          s: analysis.restrictions_subjects,
                          t: analysis.restrictions_triples,
                          highlight: false,
                        },
                        {
                          label: 'Unknown',
                          s: analysis.unknown_subjects,
                          t: analysis.unknown_triples,
                          highlight: false,
                        },
                      ] as const
                    ).map(({ label, s, t, highlight }) => (
                      <tr key={label} className="border-b last:border-0">
                        <td
                          className={cn(
                            'py-1.5 pl-3 text-muted-foreground',
                            highlight && 'font-medium text-foreground'
                          )}
                        >
                          {label}
                        </td>
                        <td
                          className={cn(
                            'py-1.5 text-right font-mono',
                            highlight && 'font-semibold text-workspace-accent'
                          )}
                        >
                          {s.toLocaleString()}
                        </td>
                        <td
                          className={cn(
                            'py-1.5 text-right font-mono',
                            highlight && 'font-semibold text-workspace-accent'
                          )}
                        >
                          {t.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between rounded-lg border bg-background px-4 py-3">
                <p className="text-sm text-muted-foreground">
                  {analysis.named_individuals_subjects === 0
                    ? 'No OWL Named Individuals found.'
                    : `Ready to import ${analysis.named_individuals_subjects.toLocaleString()} individuals.`}
                </p>
                <button
                  onClick={handleImport}
                  disabled={analysis.named_individuals_subjects === 0 || importing}
                  className={cn(
                    'ml-4 flex shrink-0 items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                    'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'
                  )}
                >
                  {importing ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <FileUp size={16} />
                  )}
                  {importing ? 'Importing…' : 'Import'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Export button ────────────────────────────────────────────────────────────

function ExportButton({
  workspaceId,
  activeGraph,
}: {
  workspaceId: string;
  activeGraph: ApiGraphInfo | null;
}) {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    if (!activeGraph) return;
    setExporting(true);
    try {
      const url = `${getApiUrl()}/api/graph/export?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}`;
      const response = await authFetch(url);
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const blob = await response.blob();
      const filename = `${activeGraph.label || 'graph'}.ttl`;
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error('Export failed', err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleExport}
      disabled={!activeGraph || exporting}
      className={cn(
        'flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground',
        (!activeGraph || exporting) && 'cursor-not-allowed opacity-50'
      )}
      title={!activeGraph ? 'Select a graph to export' : 'Export graph as TTL'}
    >
      {exporting ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <Download size={14} />
      )}
      {exporting ? 'Exporting...' : 'Export'}
    </button>
  );
}
