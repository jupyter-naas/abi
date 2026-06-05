'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  ArrowRight,
  Braces,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Code,
  Columns2,
  Database,
  Download,
  Eye,
  FileUp,
  Filter,
  Info,
  LayoutList,
  Loader2,
  Network,
  Pencil,
  RefreshCw,
  Rows2,
  Save,
  Search,
  Share2,
  Trash2,
  Upload,
  X,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { BFO_BUCKET_DEFS, getBfoBucket } from '@/lib/bfo-buckets';
import {
  appendStep,
  generateSparql,
  MANUAL_INSTANCE_SELECT_ID,
  removeStepsByType,
  upsertStep,
  upsertStepById,
  type DefaultPropertiesParams,
  type PropertyProjectionParams,
  type SparqlStep,
} from '@/lib/sparql-steps';
import { serializeTriples, type TripleExportFormat } from '@/lib/triples-export';
import { SparqlQueryPreview } from '@/components/graph/SparqlQueryPreview';
import { authFetch } from '@/stores/auth';
import {
  useKnowledgeGraphStore,
  type DiscoveryViewState,
  type GraphEdge as StoreGraphEdge,
  type GraphNode as StoreGraphNode,
  type GraphView,
} from '@/stores/knowledge-graph';

type PreviewType = 'network' | 'sparql' | 'table' | 'flat';

const PREVIEW_TYPE_DEFS: { id: PreviewType; label: string; icon: LucideIcon }[] = [
  { id: 'network', label: 'Network', icon: Share2 },
  { id: 'sparql', label: 'Sparql Query', icon: Code },
  { id: 'table', label: 'Triples', icon: Braces },
  { id: 'flat', label: 'Table', icon: LayoutList },
];

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
  bfo_bucket_uri?: string;
  bfo_bucket_label?: string;
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

interface SparqlTriple {
  s: string;
  p: string;
  o: string;
  isLiteral: boolean;
}

interface ColumnFilter {
  search: string;
  // Whitelist of values to keep. Empty = no constraint (all rows shown), which
  // is why a freshly-loaded table has every column filter unselected.
  included: Set<string>;
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

function getTripleColValue(triple: SparqlTriple, col: string): string {
  if (col === 's') return compactUri(triple.s);
  if (col === 'p') return compactUri(triple.p);
  return triple.isLiteral ? triple.o : compactUri(triple.o);
}

// ── Discovery Page ───────────────────────────────────────────────────────────

export default function DiscoveryPage() {
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
  const [selectedBucketUris, setSelectedBucketUris] = useState<string[]>([]);

  const availableBuckets = useMemo(() => {
    const seen = new Map<string, string>();
    for (const inst of instances) {
      if (inst.bfo_bucket_uri && !seen.has(inst.bfo_bucket_uri)) {
        seen.set(inst.bfo_bucket_uri, inst.bfo_bucket_label || compactUri(inst.bfo_bucket_uri));
      }
    }
    return Array.from(seen.entries())
      .map(([uri, label]) => ({ uri, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [instances]);

  useEffect(() => {
    setSelectedBucketUris(availableBuckets.map((b) => b.uri));
  }, [availableBuckets]);
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
    // Clear steps first so recording effects re-derive fresh steps from restored state.
    setSparqlSteps([]);
    extraRelationUrisRef.current = new Set();
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
    if (selectedBucketUris.length > 0) {
      const bucketSet = new Set(selectedBucketUris);
      result = result.filter((i) => i.bfo_bucket_uri && bucketSet.has(i.bfo_bucket_uri));
    }
    for (const [colId, filter] of Object.entries(columnFilters)) {
      const search = filter.search.trim().toLowerCase();
      result = result.filter((inst) => {
        const value = getInstanceColumnValue(inst, colId);
        if (filter.included.size > 0 && !filter.included.has(value)) return false;
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
  }, [instances, selectedBucketUris, columnFilters, sortState]);

  const workingInstanceUris = useMemo(() => {
    if (selectedInstanceUris.size > 0) {
      return filteredInstances
        .filter((i) => selectedInstanceUris.has(i.uri))
        .map((i) => i.uri);
    }
    return filteredInstances.slice(0, GRAPH_MAX_NODES).map((i) => i.uri);
  }, [filteredInstances, selectedInstanceUris]);

  // Excel-like filtered + sorted relation rows (Table 2 view).
  const filteredRelations = useMemo(() => {
    let result = relations;
    for (const [colId, filter] of Object.entries(relationColumnFilters)) {
      const search = filter.search.trim().toLowerCase();
      result = result.filter((rel) => {
        const value = getRelationColumnValue(rel, colId);
        if (filter.included.size > 0 && !filter.included.has(value)) return false;
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
            // Whenever the user changes their explicit row selection — including
            // clearing it back to none — show every relation for the resulting
            // working set. This keeps the relation count identical to the
            // initial (no-selection) load after a select/deselect round-trip,
            // instead of preserving a narrower previous relation-type filter.
            if (selectionChanged) {
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

    // Network shows ALL individuals from the table (capped). Rows ticked in
    // Table 1 carry a `selected` flag so the canvas can render unselected nodes
    // with a transparent/dimmed style.
    for (const inst of filteredInstances) {
      if (nodesByUri.size >= GRAPH_MAX_NODES) break;
      nodesByUri.set(inst.uri, {
        id: inst.uri,
        label: inst.label || compactUri(inst.uri),
        type: inst.class_label || compactUri(inst.class_uri),
        properties: {
          ...inst.properties,
          class_uri: inst.class_uri,
          bfo_parent_iri: inst.bfo_bucket_uri || '',
          selected: selectedInstanceUris.has(inst.uri),
        },
      });
    }

    const edges: StoreGraphEdge[] = [];
    const seenEdges = new Set<string>();
    // Network shows ALL relations from the table (capped). Every relation row
    // adds its own domain + range nodes (even if the instance row itself isn't
    // ticked in Table 1), and carries a `selected` flag from Table 2.
    for (const rel of filteredRelations) {
      if (edges.length >= GRAPH_MAX_EDGES) break;
      const relSelected = selectedRelationRowKeys.has(relationRowKey(rel));
      // Add domain node if not already in the graph.
      if (!nodesByUri.has(rel.domain_uri) && nodesByUri.size < GRAPH_MAX_NODES) {
        const domainInst = instances.find((i) => i.uri === rel.domain_uri);
        nodesByUri.set(rel.domain_uri, {
          id: rel.domain_uri,
          label: rel.domain_label || compactUri(rel.domain_uri),
          type: rel.domain_class_label || compactUri(rel.domain_class_uri || ''),
          properties: {
            class_uri: rel.domain_class_uri,
            bfo_parent_iri: domainInst?.bfo_bucket_uri || '',
            selected: selectedInstanceUris.has(rel.domain_uri),
          },
        });
      }
      if (!nodesByUri.has(rel.domain_uri)) continue;
      // Add range node if not already in the graph.
      if (!nodesByUri.has(rel.range_uri) && nodesByUri.size < GRAPH_MAX_NODES) {
        const rangeInst = instances.find((i) => i.uri === rel.range_uri);
        nodesByUri.set(rel.range_uri, {
          id: rel.range_uri,
          label: rel.range_label || compactUri(rel.range_uri),
          type: rel.range_class_label || compactUri(rel.range_class_uri || ''),
          properties: {
            class_uri: rel.range_class_uri,
            bfo_parent_iri: rangeInst?.bfo_bucket_uri || '',
            selected: selectedInstanceUris.has(rel.range_uri),
          },
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
        properties: { selected: relSelected },
      });
    }

    return { graphNodes: Array.from(nodesByUri.values()), graphEdges: edges };
  }, [
    instances,
    filteredInstances,
    filteredRelations,
    selectedInstanceUris,
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

  const clearAllFilters = useCallback(() => {
    // SPARQL pipeline + relation-derived instance tracking
    setSparqlSteps([]);
    extraRelationUrisRef.current = new Set();
    prevSelectedInstanceUrisRef.current = new Set();
    prevSelectedRelationRowKeysRef.current = new Set();
    prevSelectedInstancesKeyRef.current = '';

    // Filters / selection — match first-load discovery defaults (all classes, default props, no search)
    setSelectedClassUris(classes.length > 0 ? classes.map((c) => c.uri) : []);
    setSelectedPropertyUris(DEFAULT_PROPERTY_URIS);
    setSelectedRelationUris([]);
    setSelectedBucketUris(availableBuckets.map((b) => b.uri));
    setSearch('');
    setDebouncedSearch('');
    setSelectedInstanceUris(new Set());
    setHighlightedNodeUri(null);
    setColumnFilters({});
    setSortState(null);
    setHiddenColumns(new Set());
    setRelationColumnFilters({});
    setRelationSortState(null);
    setSelectedRelationRowKeys(new Set());
    setInstances([]);
    setInstancesLoading(classes.length > 0);
    setInstancesError(null);
    setRelations([]);
    setRelationsLoading(false);
    setRelationsError(null);
    setActiveSavedView(null);
    lastAppliedViewIdRef.current = null;
  }, [availableBuckets, classes]);

  // ── SPARQL step recording ──────────────────────────────────────────────────

  const [sparqlSteps, setSparqlSteps] = useState<SparqlStep[]>([]);
  const prevSelectedInstanceUrisRef = useRef<Set<string>>(new Set());
  const prevSelectedRelationRowKeysRef = useRef<Set<string>>(new Set());
  // Tracks URIs that were auto-checked from relations so they're recorded in a
  // separate appended step rather than editing the manual instance_select step.
  const extraRelationUrisRef = useRef<Set<string>>(new Set());
  const activeGraphRef = useRef<typeof activeGraph>(null);
  activeGraphRef.current = activeGraph;
  // Always-fresh snapshot of filteredRelations for the relation step effect.
  const filteredRelationsRef = useRef(filteredRelations);
  filteredRelationsRef.current = filteredRelations;

  const graphUri = activeGraph?.uri ?? '';

  // Reset steps when the active graph changes.
  useEffect(() => {
    setSparqlSteps([]);
    prevSelectedInstanceUrisRef.current = new Set();
    prevSelectedRelationRowKeysRef.current = new Set();
  }, [graphUri]);

  // Step 1 — search
  useEffect(() => {
    if (!graphUri) return;
    const q = debouncedSearch.trim();
    if (q) {
      const params = { type: 'search' as const, search: q, graphUri };
      setSparqlSteps((prev) =>
        upsertStep(prev, { type: 'search', label: `Search: "${q}"`, sparql: generateSparql(params), params })
      );
    } else {
      setSparqlSteps((prev) => removeStepsByType(prev, 'search'));
    }
  }, [debouncedSearch, graphUri]);

  // Step 2 — class filter (only when it's a real subset, not all-selected)
  useEffect(() => {
    if (!graphUri || classes.length === 0) return;
    const isAll = selectedClassUris.length === classes.length;
    if (!isAll && selectedClassUris.length > 0) {
      const classLabels = selectedClassUris.map(
        (uri) => classes.find((c) => c.uri === uri)?.label ?? compactUri(uri)
      );
      const labelStr =
        classLabels.length <= 2
          ? classLabels.join(', ')
          : `${classLabels.slice(0, 2).join(', ')} +${classLabels.length - 2}`;
      const params = {
        type: 'class_filter' as const,
        classUris: selectedClassUris,
        classLabels,
        graphUri,
      };
      setSparqlSteps((prev) =>
        upsertStep(prev, { type: 'class_filter', label: `Classes: ${labelStr}`, sparql: generateSparql(params), params })
      );
    } else {
      setSparqlSteps((prev) => removeStepsByType(prev, 'class_filter'));
    }
  }, [selectedClassUris.join(','), classes.length, graphUri]);

  // Step 3 — property filter (only when non-default)
  useEffect(() => {
    if (!graphUri) return;
    const isDefault =
      selectedPropertyUris.length === DEFAULT_PROPERTY_URIS.length &&
      DEFAULT_PROPERTY_URIS.every((u) => selectedPropertyUris.includes(u));
    if (!isDefault && selectedPropertyUris.length > 0) {
      const params = { type: 'property_filter' as const, propertyUris: selectedPropertyUris, graphUri };
      setSparqlSteps((prev) =>
        upsertStep(prev, {
          type: 'property_filter',
          label: `Properties: ${selectedPropertyUris.length} selected`,
          sparql: generateSparql(params),
          params,
        })
      );
    } else {
      setSparqlSteps((prev) => removeStepsByType(prev, 'property_filter'));
    }
  }, [selectedPropertyUris.join(','), graphUri]);

  // Step 4 — instance select + exclusion
  useEffect(() => {
    if (!graphUri) return;
    const prev = prevSelectedInstanceUrisRef.current;
    const curr = selectedInstanceUris;

    // Detect explicit removals from a non-empty prior set → exclusion step
    if (prev.size > 0 && curr.size < prev.size) {
      const removed = Array.from(prev).filter((uri) => !curr.has(uri));
      if (removed.length > 0) {
        const params = { type: 'exclusion' as const, excludedInstanceUris: removed, excludedRelationRowKeys: [] };
        setSparqlSteps((p) =>
          appendStep(p, {
            type: 'exclusion',
            label: `Exclude ${removed.length} individual${removed.length > 1 ? 's' : ''}`,
            sparql: generateSparql(params),
            params,
          })
        );
      }
    }

    if (curr.size > 0) {
      // Exclude URIs that were auto-added from relations — those get their own appended step.
      const manualUris = Array.from(curr).filter((u) => !extraRelationUrisRef.current.has(u));
      if (manualUris.length > 0) {
        const params = { type: 'instance_select' as const, instanceUris: manualUris, graphUri };
        setSparqlSteps((p) =>
          upsertStepById(p, MANUAL_INSTANCE_SELECT_ID, {
            type: 'instance_select',
            label: `Select ${manualUris.length} individual${manualUris.length > 1 ? 's' : ''}`,
            sparql: generateSparql(params),
            params,
          })
        );
      }
    } else if (prev.size > 0) {
      setSparqlSteps((p) => removeStepsByType(p, 'instance_select'));
      extraRelationUrisRef.current = new Set();
    }

    prevSelectedInstanceUrisRef.current = new Set(curr);
  }, [selectedInstanceUris, graphUri]);

  // Step 5 — relation select (driven by selectedRelationRowKeys growing)
  useEffect(() => {
    if (!graphUri) return;
    const prev = prevSelectedRelationRowKeysRef.current;
    const curr = selectedRelationRowKeys;

    // Removals from a non-empty prior set → exclusion step
    if (prev.size > 0 && curr.size < prev.size) {
      const removed = Array.from(prev).filter((k) => !curr.has(k));
      if (removed.length > 0) {
        const params = { type: 'exclusion' as const, excludedInstanceUris: [], excludedRelationRowKeys: removed };
        setSparqlSteps((p) =>
          appendStep(p, {
            type: 'exclusion',
            label: `Exclude ${removed.length} relation row${removed.length > 1 ? 's' : ''}`,
            sparql: generateSparql(params),
            params,
          })
        );
      }
    }

    if (curr.size > 0 && selectedRelationUris.length > 0) {
      const rowKeys = Array.from(curr);
      // Compute excluded instances from relation rows not in the selection.
      // Empty array = all rows selected → no FILTER in the generated SPARQL.
      const allRels = filteredRelationsRef.current;
      const excludedInstSet = new Set<string>();
      for (const rel of allRels) {
        const key = `${rel.role}|${rel.domain_uri}|${rel.relation_uri}|${rel.range_uri}`;
        if (!curr.has(key)) {
          if (rel.domain_uri) excludedInstSet.add(rel.domain_uri);
          if (rel.range_uri)  excludedInstSet.add(rel.range_uri);
        }
      }
      const params = {
        type: 'relation_select' as const,
        relationUris: selectedRelationUris,
        selectedRowKeys: rowKeys,
        excludedInstanceUris: Array.from(excludedInstSet),
        graphUri,
      };
      setSparqlSteps((p) =>
        upsertStep(p, {
          type: 'relation_select',
          label: `Relations: ${rowKeys.length} row${rowKeys.length > 1 ? 's' : ''} · ${selectedRelationUris.length} type${selectedRelationUris.length > 1 ? 's' : ''}`,
          sparql: generateSparql(params),
          params,
        })
      );
    } else if (prev.size > 0 && curr.size === 0) {
      setSparqlSteps((p) => removeStepsByType(p, 'relation_select'));
      extraRelationUrisRef.current = new Set();
    }

    prevSelectedRelationRowKeysRef.current = new Set(curr);
  }, [selectedRelationRowKeys, graphUri]);

  // Clear all steps when both individuals and relations are deselected.
  useEffect(() => {
    if (selectedInstanceUris.size === 0 && selectedRelationRowKeys.size === 0) {
      setSparqlSteps([]);
      extraRelationUrisRef.current = new Set();
    }
  }, [selectedInstanceUris, selectedRelationRowKeys]);

  // Step 6 — default properties (recorded once instances are selected, always at the end).
  useEffect(() => {
    if (!graphUri) return;
    if (selectedInstanceUris.size > 0) {
      const params: DefaultPropertiesParams = { type: 'default_properties', graphUri };
      setSparqlSteps((p) => {
        const without = removeStepsByType(p, 'default_properties');
        return appendStep(without, {
          type: 'default_properties',
          label: 'Default properties (rdf:type, rdfs:label)',
          sparql: generateSparql(params),
          params,
        });
      });
    } else {
      setSparqlSteps((p) => removeStepsByType(p, 'default_properties'));
    }
  }, [selectedInstanceUris.size > 0, graphUri]);

  // Step 7 — property projections: one per selected class when a non-default
  // property filter is active. Re-appended at the end on every change.
  useEffect(() => {
    if (!graphUri) return;
    const isAllClasses = selectedClassUris.length === classes.length;
    const isDefaultProps =
      selectedPropertyUris.length === DEFAULT_PROPERTY_URIS.length &&
      DEFAULT_PROPERTY_URIS.every((u) => selectedPropertyUris.includes(u));

    setSparqlSteps((p) => {
      const without = removeStepsByType(p, 'property_projection');
      if (isAllClasses || selectedClassUris.length === 0 || isDefaultProps || selectedPropertyUris.length === 0) {
        return without;
      }
      let next = without;
      for (const classUri of selectedClassUris) {
        const classLabel = classes.find((c) => c.uri === classUri)?.label ?? compactUri(classUri);
        const params: PropertyProjectionParams = {
          type: 'property_projection',
          classUri,
          classLabel,
          propertyUris: selectedPropertyUris,
          graphUri,
        };
        next = appendStep(next, {
          type: 'property_projection',
          label: `${classLabel} → ${selectedPropertyUris.length} prop${selectedPropertyUris.length > 1 ? 's' : ''}`,
          sparql: generateSparql(params),
          params,
        });
      }
      return next;
    });
  }, [selectedClassUris.join(','), selectedPropertyUris.join(','), classes.length, graphUri]);

  // Called by DiscoveryPane when individuals are auto-checked from relation rows.
  // Appends a dedicated step instead of editing the manual instance_select step.
  const handleNewInstancesFromRelations = useCallback((newUris: string[]) => {
    const graphUri = activeGraphRef.current?.uri;
    if (!graphUri || newUris.length === 0) return;
    const next = new Set(extraRelationUrisRef.current);
    for (const u of newUris) next.add(u);
    extraRelationUrisRef.current = next;
    const params = { type: 'instance_select' as const, instanceUris: newUris, graphUri };
    setSparqlSteps((prev) =>
      appendStep(prev, {
        type: 'instance_select',
        label: `Data properties of ${newUris.length} individual${newUris.length > 1 ? 's' : ''} found via relations`,
        sparql: generateSparql(params),
        params,
      })
    );
  }, []);

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
      sparqlSteps,
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
                onClick={() => router.push(`/workspace/${workspaceId}/graph/network`)}
                className="flex items-center gap-2 rounded-md px-3 py-1 text-sm text-muted-foreground hover:bg-background"
              >
                <Network size={14} />
                Network
              </button>
              <button
                onClick={() => {
                  router.push(`/workspace/${workspaceId}/graph/discovery`);
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
                  router.push(`/workspace/${workspaceId}/graph/discovery`);
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
                availableBuckets={availableBuckets}
                selectedBucketUris={selectedBucketUris}
                onToggleBucket={(uri) =>
                  setSelectedBucketUris((prev) =>
                    prev.includes(uri) ? prev.filter((u) => u !== uri) : [...prev, uri]
                  )
                }
                onSetSelectedBuckets={setSelectedBucketUris}
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
                sparqlSteps={sparqlSteps}
                onRemoveStep={(id) => setSparqlSteps((prev) => prev.filter((s) => s.id !== id))}
                onNewInstancesFromRelations={handleNewInstancesFromRelations}
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
  availableBuckets: { uri: string; label: string }[];
  selectedBucketUris: string[];
  onToggleBucket: (uri: string) => void;
  onSetSelectedBuckets: (uris: string[]) => void;
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
  sparqlSteps: SparqlStep[];
  onRemoveStep: (id: string) => void;
  onNewInstancesFromRelations: (newUris: string[]) => void;
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
    availableBuckets,
    selectedBucketUris,
    onToggleBucket,
    onSetSelectedBuckets,
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
    sparqlSteps,
    onRemoveStep,
    onNewInstancesFromRelations,
  } = props;

  // Bump stabilizeKey whenever the visible graph composition changes so
  // vis-network re-runs physics and auto-fits to the canvas.
  const graphCompositionKey = useMemo(() => {
    const nodeIds = graphNodes.map((n) => n.id).sort().join('|');
    const edgeIds = graphEdges.map((e) => e.id).sort().join('|');
    // Include the full filtered dataset size so the class preview (which
    // aggregates every row/relation, not just the capped network) re-stabilizes
    // when rows are added beyond the network cap.
    return `${nodeIds}::${edgeIds}::${filteredInstances.length}:${filteredRelations.length}`;
  }, [graphNodes, graphEdges, filteredInstances.length, filteredRelations.length]);
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
      setOpenSections(['instances', 'relations']);
    }
    if (!activeSavedViewId) {
      prevAppliedViewIdRef.current = null;
    }
  }, [activeSavedViewId]);

  // Right-panel "Preview": up to two of network / sparql / table shown at once.
  const [selectedPreviews, setSelectedPreviews] = useState<PreviewType[]>(['network']);
  const [previewSplitOrientation, setPreviewSplitOrientation] =
    useState<'horizontal' | 'vertical'>('vertical');
  const [previewSize, setPreviewSize] = useState<'full' | 'middle' | 'collapsed'>('middle');

  // CSV export dialog state
  const [csvExportOpen, setCsvExportOpen] = useState(false);
  const [csvEncoding, setCsvEncoding] = useState<'utf-8' | 'utf-8-bom'>('utf-8');
  const [csvSeparator, setCsvSeparator] = useState(';');
  const [csvDecimal, setCsvDecimal] = useState(',');

  // Selecting Table ('flat') forces full-width; deselecting restores middle.
  const togglePreview = (id: PreviewType) => {
    if (id === 'flat') {
      if (selectedPreviews.includes('flat')) {
        setPreviewSize('middle');
      } else {
        setPreviewSize('full');
      }
    }
    setSelectedPreviews((prev) => {
      if (prev.includes(id)) return prev.filter((p) => p !== id);
      if (prev.length >= 2) return prev;
      return [...prev, id];
    });
  };

  const [networkViewMode, setNetworkViewMode] = useState<'individuals' | 'classes'>('classes');

  // Class preview aggregates EVERY row/relation in the tables — not just the
  // (capped) individuals drawn in the network — so it always reflects the full
  // filtered dataset.
  const classGraphNodes = useMemo<StoreGraphNode[]>(() => {
    // A class counts as selected when at least one of its individuals is ticked
    // in the Individuals table — so the Classes view dims the same way.
    const selectedClassUriSet = new Set<string>();
    for (const inst of filteredInstances) {
      if (selectedInstanceUris.has(inst.uri)) {
        selectedClassUriSet.add(inst.class_uri || inst.class_label || '');
      }
    }
    const classCounts = new Map<string, { label: string; count: number; bfoParentIri: string }>();
    for (const inst of filteredInstances) {
      const classUri = inst.class_uri || inst.class_label || '';
      if (!classUri) continue;
      const existing = classCounts.get(classUri);
      if (existing) { existing.count++; }
      else { classCounts.set(classUri, { label: inst.class_label || compactUri(inst.class_uri), count: 1, bfoParentIri: inst.bfo_bucket_uri || '' }); }
    }
    // Ensure classes referenced only by relations still appear as nodes so
    // every class edge has both endpoints.
    for (const rel of filteredRelations) {
      for (const [uri, label] of [
        [rel.domain_class_uri, rel.domain_class_label],
        [rel.range_class_uri, rel.range_class_label],
      ] as [string | undefined, string | undefined][]) {
        const classUri = uri || label || '';
        if (!classUri || classCounts.has(classUri)) continue;
        classCounts.set(classUri, { label: label || compactUri(uri || ''), count: 0, bfoParentIri: '' });
      }
    }
    return Array.from(classCounts.entries()).map(([classUri, { label, count, bfoParentIri }]) => ({
      id: classUri || label,
      label: count > 0 ? `${label} (${count})` : label,
      type: label,
      properties: { class_uri: classUri, bfo_parent_iri: bfoParentIri, selected: selectedClassUriSet.has(classUri) },
    }));
  }, [filteredInstances, filteredRelations, selectedInstanceUris]);

  const classGraphEdges = useMemo<StoreGraphEdge[]>(() => {
    const edgeCounts = new Map<string, { domainClass: string; rangeClass: string; label: string; count: number; selected: boolean }>();
    for (const rel of filteredRelations) {
      const domainClass = rel.domain_class_uri || rel.domain_class_label || '';
      const rangeClass = rel.range_class_uri || rel.range_class_label || '';
      if (!domainClass || !rangeClass) continue;
      const label = rel.relation_label || compactUri(rel.relation_uri);
      const key = `${domainClass}|${label}|${rangeClass}`;
      // A class relation is selected when any underlying relation row is ticked.
      const relSelected = selectedRelationRowKeys.has(relationRowKey(rel));
      const existing = edgeCounts.get(key);
      if (existing) { existing.count++; existing.selected = existing.selected || relSelected; }
      else { edgeCounts.set(key, { domainClass, rangeClass, label, count: 1, selected: relSelected }); }
    }
    return Array.from(edgeCounts.entries()).map(([key, { domainClass, rangeClass, label, count, selected }]) => ({
      id: key,
      source: domainClass,
      target: rangeClass,
      type: label,
      label: `${label} (${count})`,
      properties: { selected },
    }));
  }, [filteredRelations, selectedRelationRowKeys]);

  const [instancePage, setInstancePage] = useState(0);
  const [instancePageSize, setInstancePageSize] = useState(20);
  const [relationPage, setRelationPage] = useState(0);
  const [relationPageSize, setRelationPageSize] = useState(20);

  // Synthesize extra instances from selected relation domain/range URIs not already in filteredInstances.
  // Computed inside DiscoveryPane to avoid circular dependency with the relations API fetch.
  const extraInstancesFromRelations = useMemo<ApiDiscoveryInstance[]>(() => {
    if (selectedRelationRowKeys.size === 0) return [];
    const existingUris = new Set(filteredInstances.map((i) => i.uri));
    const extra = new Map<string, ApiDiscoveryInstance>();
    for (const key of selectedRelationRowKeys) {
      const rel = filteredRelations.find((r) => relationRowKey(r) === key);
      if (!rel) continue;
      for (const [uri, label, class_uri, class_label] of [
        [rel.domain_uri, rel.domain_label, rel.domain_class_uri ?? '', rel.domain_class_label ?? ''],
        [rel.range_uri,  rel.range_label,  rel.range_class_uri  ?? '', rel.range_class_label  ?? ''],
      ] as [string, string, string, string][]) {
        if (uri && !existingUris.has(uri) && !extra.has(uri)) {
          extra.set(uri, { uri, label: label || compactUri(uri), class_uri, class_label, properties: {} });
        }
      }
    }
    return Array.from(extra.values());
  }, [filteredInstances, filteredRelations, selectedRelationRowKeys]);

  const displayInstances = useMemo(
    () => (extraInstancesFromRelations.length > 0 ? [...filteredInstances, ...extraInstancesFromRelations] : filteredInstances),
    [filteredInstances, extraInstancesFromRelations]
  );

  // The individuals network is only legible for small sets; hide that toggle
  // (and fall back to the classes view) once the table grows beyond 20 rows.
  const individualsViewAvailable = displayInstances.length <= 20;
  useEffect(() => {
    if (!individualsViewAvailable && networkViewMode === 'individuals') {
      setNetworkViewMode('classes');
    }
  }, [individualsViewAvailable, networkViewMode]);

  // Auto-check synthetic instances that appear from selected relation rows.
  const selectedInstanceUrisRef = useRef(selectedInstanceUris);
  selectedInstanceUrisRef.current = selectedInstanceUris;

  useEffect(() => {
    if (extraInstancesFromRelations.length === 0) return;
    const current = selectedInstanceUrisRef.current;
    const newUris = extraInstancesFromRelations.map((i) => i.uri).filter((u) => !current.has(u));
    if (newUris.length === 0) return;
    // Record a dedicated step for these before updating selection so the ref is
    // set before the instance_select effect fires in GraphPage.
    onNewInstancesFromRelations(newUris);
    const next = new Set(current);
    for (const uri of newUris) next.add(uri);
    onSetSelectedInstances(next);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extraInstancesFromRelations]);

  const selectedInstancesByClass = useMemo(() => {
    if (selectedInstanceUris.size === 0) return [] as { label: string; count: number }[];
    const map = new Map<string, { label: string; count: number }>();
    for (const uri of selectedInstanceUris) {
      const inst = displayInstances.find((i) => i.uri === uri) ?? instances.find((i) => i.uri === uri);
      if (!inst) continue;
      const key = inst.class_uri || inst.class_label;
      const existing = map.get(key);
      if (existing) { existing.count++; }
      else { map.set(key, { label: inst.class_label || compactUri(inst.class_uri), count: 1 }); }
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  }, [selectedInstanceUris, displayInstances, instances]);

  useEffect(() => { setInstancePage(0); }, [displayInstances]);
  useEffect(() => { setRelationPage(0); }, [filteredRelations]);

  const pagedInstances = useMemo(
    () => displayInstances.slice(instancePage * instancePageSize, (instancePage + 1) * instancePageSize),
    [displayInstances, instancePage, instancePageSize]
  );

  const pagedRelations = useMemo(
    () => filteredRelations.slice(relationPage * relationPageSize, (relationPage + 1) * relationPageSize),
    [filteredRelations, relationPage, relationPageSize]
  );


  const previewRelations = useMemo(
    () => filteredRelations.filter((r) => selectedRelationRowKeys.has(relationRowKey(r))),
    [filteredRelations, selectedRelationRowKeys]
  );

  // ── Triples derived from preview selection ─────────────────────────────────

  const RDF_TYPE = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type';
  const OWL_NAMED_INDIVIDUAL = 'http://www.w3.org/2002/07/owl#NamedIndividual';
  const MAX_TRIPLES = 10_000;

  // All triples from every visible instance (class triple + loaded data-property triples)
  // plus the user-selected relation rows. Selection drives the s-column filter, not this source.
  const allTriples = useMemo<SparqlTriple[]>(() => {
    const triples: SparqlTriple[] = [];
    for (const inst of filteredInstances) {
      // rdf:type owl:NamedIndividual — always emitted for every instance
      triples.push({ s: inst.uri, p: RDF_TYPE, o: OWL_NAMED_INDIVIDUAL, isLiteral: false });
      // rdf:type <class> — always present when class is known
      if (inst.class_uri) {
        triples.push({ s: inst.uri, p: RDF_TYPE, o: inst.class_uri, isLiteral: false });
      }
      // Data properties loaded by the current property selection
      const addedProps = new Set<string>();
      for (const [propUri, value] of Object.entries(inst.properties)) {
        if (value != null && String(value) !== '') {
          triples.push({ s: inst.uri, p: propUri, o: String(value), isLiteral: true });
          addedProps.add(propUri);
        }
      }
      // rdfs:label — guarantee it is present even when the API returned the
      // label via inst.label but did not populate inst.properties[RDFS_LABEL]
      if (!addedProps.has(RDFS_LABEL) && inst.label) {
        triples.push({ s: inst.uri, p: RDFS_LABEL, o: inst.label, isLiteral: true });
      }
    }
    const seen = new Set<string>();
    for (const rel of previewRelations) {
      const key = `${rel.domain_uri}|${rel.relation_uri}|${rel.range_uri}`;
      if (!seen.has(key)) {
        seen.add(key);
        triples.push({ s: rel.domain_uri, p: rel.relation_uri, o: rel.range_uri, isLiteral: false });
      }
    }
    if (triples.length > MAX_TRIPLES) {
      return triples.slice(0, MAX_TRIPLES);
    }
    return triples;
  }, [filteredInstances, previewRelations]);

  const [tripleColumnFilters, setTripleColumnFilters] = useState<Record<string, ColumnFilter>>({});
  const [tripleSortState, setTripleSortState] = useState<SortState | null>(null);

  // ── Flat instances table (preview "Table") ─────────────────────────────────

  const [flatTableColumnFilters, setFlatTableColumnFilters] = useState<Record<string, ColumnFilter>>({});
  const [flatTableSortState, setFlatTableSortState] = useState<SortState | null>(null);
  const [flatTablePage, setFlatTablePage] = useState(0);
  const [flatTablePageSize, setFlatTablePageSize] = useState(20);

  const filteredInstancesRef = useRef(filteredInstances);
  filteredInstancesRef.current = filteredInstances;

  // When the user checks/unchecks instance rows, auto-sync the triple table's s-column
  // filter so only the selected subjects are visible (selection = filter on subject).
  useEffect(() => {
    if (selectedInstanceUris.size === 0) {
      setTripleColumnFilters((prev) => {
        if (!prev.s) return prev;
        const next = { ...prev };
        delete next.s;
        return next;
      });
    } else {
      const selectedCompact = new Set(Array.from(selectedInstanceUris).map((u) => compactUri(u)));
      setTripleColumnFilters((prev) => ({ ...prev, s: { search: '', included: selectedCompact } }));
    }
  }, [selectedInstanceUris, filteredInstances]);
  const [triplePage, setTriplePage] = useState(0);
  const [triplePageSize, setTriplePageSize] = useState(20);

  const tripleUniqueValues = useMemo(() => ({
    s: [...new Set(allTriples.map((t) => compactUri(t.s)))].sort(),
    p: [...new Set(allTriples.map((t) => compactUri(t.p)))].sort(),
    o: [...new Set(allTriples.map((t) => (t.isLiteral ? t.o : compactUri(t.o))))].sort(),
  }), [allTriples]);

  const filteredTriples = useMemo(() => {
    let result = allTriples;
    for (const [col, filter] of Object.entries(tripleColumnFilters)) {
      const s = filter.search.trim().toLowerCase();
      result = result.filter((t) => {
        const val = getTripleColValue(t, col);
        if (filter.included.size > 0 && !filter.included.has(val)) return false;
        if (s && !val.toLowerCase().includes(s)) return false;
        return true;
      });
    }
    if (tripleSortState) {
      const dir = tripleSortState.direction === 'asc' ? 1 : -1;
      result = [...result].sort((a, b) => {
        const av = getTripleColValue(a, tripleSortState.column).toLowerCase();
        const bv = getTripleColValue(b, tripleSortState.column).toLowerCase();
        if (av < bv) return -1 * dir;
        if (av > bv) return 1 * dir;
        return 0;
      });
    }
    return result;
  }, [allTriples, tripleColumnFilters, tripleSortState]);

  useEffect(() => { setTriplePage(0); }, [filteredTriples.length]);

  const pagedTriples = useMemo(
    () => filteredTriples.slice(triplePage * triplePageSize, (triplePage + 1) * triplePageSize),
    [filteredTriples, triplePage, triplePageSize]
  );

  const baseColumns = [
    { id: 'uri', label: 'uri' },
    { id: RDFS_LABEL, label: 'rdfs:label' },
    { id: 'class', label: 'rdf:type' },
    { id: 'bfo_bucket', label: 'BFO bucket' },
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

  // ── Flat table computed data ───────────────────────────────────────────────

  // Instances to show in the flat table = checked individuals + domain/range of checked relation rows.
  const flatTableInstances = useMemo<ApiDiscoveryInstance[]>(() => {
    if (selectedInstanceUris.size === 0 && selectedRelationRowKeys.size === 0) return [];
    const allInst = [...instances, ...displayInstances];
    const byUri = new Map<string, ApiDiscoveryInstance>();
    for (const i of allInst) byUri.set(i.uri, i);
    const uriSet = new Set<string>(selectedInstanceUris);
    for (const rel of previewRelations) {
      uriSet.add(rel.domain_uri);
      uriSet.add(rel.range_uri);
    }
    return [...uriSet].flatMap((uri) => {
      const inst = byUri.get(uri);
      return inst ? [inst] : [];
    });
  }, [selectedInstanceUris, selectedRelationRowKeys, previewRelations, instances, displayInstances]);

  const flatTablePropertyCols = useMemo(
    () => selectedPropertyUris
      .filter((uri) => uri !== RDFS_LABEL)
      .map((uri) => ({
        id: uri,
        label: properties.find((p) => p.uri === uri)?.label ?? compactUri(uri),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedPropertyUris.join(','), properties]
  );

  // Derive prefix from the actual class label of selected instances.
  // Single class → use it (e.g. "Agent"); mixed → "class".
  const flatTableClassPrefix = useMemo(() => {
    const labels = new Set(flatTableInstances.map((i) => i.class_label).filter(Boolean));
    return labels.size === 1 ? [...labels][0] : 'class';
  }, [flatTableInstances]);

  // One entry per unique relation type from selected relations.
  // Column label: {DomainClass}.{relLabel}.{RangeClass}  (e.g. Agent.has_role.AgentRole)
  // Same-class relations (Agent→Agent) get a "1" suffix on the range class (Agent1).
  const flatTableRelTypes = useMemo(() => {
    const map = new Map<string, {
      relUri: string; colId: string; colLabel: string; isSameClass: boolean;
    }>();
    for (const rel of previewRelations) {
      if (!map.has(rel.relation_uri)) {
        const domainCls = rel.domain_class_label || compactUri(rel.domain_class_uri || '') || 'class';
        const relLabel  = rel.relation_label || compactUri(rel.relation_uri);
        const isSameClass = Boolean(
          (rel.domain_class_uri  && rel.domain_class_uri  === rel.range_class_uri) ||
          (!rel.domain_class_uri && rel.domain_class_label && rel.domain_class_label === rel.range_class_label)
        );
        const rangeCls = rel.range_class_label || compactUri(rel.range_class_uri || '') || 'related';
        map.set(rel.relation_uri, {
          relUri: rel.relation_uri,
          colId: `rel__${rel.relation_uri}`,
          // e.g. "Agent.has_role.AgentRole" or "Agent.related_to.Agent1"
          colLabel: `${domainCls}.${relLabel}.${isSameClass ? `${rangeCls}1` : rangeCls}`,
          isSameClass,
        });
      }
    }
    return [...map.values()];
  }, [previewRelations]);

  // Column defs: id uses safe JS keys, label uses dotted notation shown in header.
  // Relation columns store the destination URI; no separate range-class column groups.
  const flatTableCols = useMemo<{ id: string; label: string }[]>(() => [
    { id: 'class_uri',   label: `${flatTableClassPrefix}.uri` },
    { id: 'class_label', label: `${flatTableClassPrefix}.label` },
    // one column per selected data property
    ...flatTablePropertyCols.map((c) => ({ id: c.id, label: `${flatTableClassPrefix}.${c.label}` })),
    // one column per unique relation type — value = destination URI
    ...flatTableRelTypes.map((rt) => ({ id: rt.colId, label: rt.colLabel })),
  ], [flatTableClassPrefix, flatTablePropertyCols, flatTableRelTypes]);

  const allFlatTableRows = useMemo<Record<string, string>[]>(() => {
    const relTypeMap = new Map(flatTableRelTypes.map((rt) => [rt.relUri, rt]));
    const rows: Record<string, string>[] = [];

    for (const inst of flatTableInstances) {
      const base: Record<string, string> = {
        class_uri:       compactUri(inst.uri),
        _class_uri_full: inst.uri,
        class_label:     inst.label || '',
      };
      for (const propUri of selectedPropertyUris) {
        if (propUri !== RDFS_LABEL) {
          base[propUri] = formatPropertyValue(inst.properties[propUri]);
        }
      }

      // Relations where this instance is the domain.
      const domainRels = previewRelations.filter((r) => r.domain_uri === inst.uri);
      // Same-class relations where this instance is the range → show in reverse.
      const reverseRels = previewRelations.filter((r) => {
        const rt = relTypeMap.get(r.relation_uri);
        return rt?.isSameClass && r.range_uri === inst.uri;
      });

      if (domainRels.length === 0 && reverseRels.length === 0) {
        rows.push({ ...base });
      } else {
        for (const rel of domainRels) {
          const rt = relTypeMap.get(rel.relation_uri);
          if (!rt) continue;
          rows.push({ ...base, [rt.colId]: compactUri(rel.range_uri) });
        }
        for (const rel of reverseRels) {
          const rt = relTypeMap.get(rel.relation_uri);
          if (!rt) continue;
          rows.push({ ...base, [rt.colId]: compactUri(rel.domain_uri) });
        }
      }
    }
    return rows;
  }, [flatTableInstances, previewRelations, selectedPropertyUris, flatTableRelTypes]);

  const filteredFlatTableRows = useMemo(() => {
    let result = allFlatTableRows;
    for (const [colId, filter] of Object.entries(flatTableColumnFilters)) {
      const s = filter.search.trim().toLowerCase();
      result = result.filter((row) => {
        const val = row[colId] ?? '';
        if (filter.included.size > 0 && !filter.included.has(val)) return false;
        if (s && !val.toLowerCase().includes(s)) return false;
        return true;
      });
    }
    if (flatTableSortState) {
      const dir = flatTableSortState.direction === 'asc' ? 1 : -1;
      result = [...result].sort((a, b) => {
        const av = (a[flatTableSortState.column] ?? '').toLowerCase();
        const bv = (b[flatTableSortState.column] ?? '').toLowerCase();
        if (av < bv) return -1 * dir;
        if (av > bv) return 1 * dir;
        return 0;
      });
    }
    return result;
  }, [allFlatTableRows, flatTableColumnFilters, flatTableSortState]);

  useEffect(() => { setFlatTablePage(0); }, [filteredFlatTableRows.length]);

  const pagedFlatTableRows = useMemo(
    () => filteredFlatTableRows.slice(flatTablePage * flatTablePageSize, (flatTablePage + 1) * flatTablePageSize),
    [filteredFlatTableRows, flatTablePage, flatTablePageSize]
  );

  const flatTableUniqueValues = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const col of flatTableCols) {
      const set = new Set<string>();
      for (const row of allFlatTableRows) set.add(row[col.id] ?? '');
      out[col.id] = Array.from(set).sort();
    }
    return out;
  }, [allFlatTableRows, flatTableCols]);

  // ── Sync Individuals column filters with checkbox selection ────────────────
  // When the user checks rows, every column filter auto-updates so only the
  // selected rows' values remain visible (selection = filter). Clearing the
  // selection resets all column filters.
  const allColumnIdsRef = useRef<string[]>([]);
  useEffect(() => {
    allColumnIdsRef.current = allColumns.map((c) => c.id);
  });

  const instancesRef = useRef(instances);
  instancesRef.current = instances;

  useEffect(() => {
    const insts = instancesRef.current;
    if (selectedInstanceUris.size === 0) {
      onColumnFiltersChange({});
      return;
    }
    const selectedRows = insts.filter((i) => selectedInstanceUris.has(i.uri));
    if (selectedRows.length === 0) return;

    const newFilters: Record<string, ColumnFilter> = {};
    for (const colId of [RDFS_LABEL, 'class']) {
      const selectedVals = new Set(selectedRows.map((i) => getInstanceColumnValue(i, colId)));
      if (selectedVals.size > 0) newFilters[colId] = { search: '', included: selectedVals };
    }
    onColumnFiltersChange(newFilters);
  }, [selectedInstanceUris, instances]);

  // Selecting new rows in the tables closes any open inspector (per UX spec:
  // inspector opens on URI click, closes via its button or on a new selection).
  const closeInspector = () => setInspectedInstance(null);
  const handleToggleInstance = (uri: string) => { closeInspector(); onToggleInstance(uri); };
  const handleSetSelectedInstances = (uris: Set<string>) => { closeInspector(); onSetSelectedInstances(uris); };
  const handleToggleRelationRow = (key: string) => { closeInspector(); onToggleRelationRow(key); };
  const handleSetSelectedRelationRows = (keys: Set<string>) => { closeInspector(); onSetSelectedRelationRows(keys); };

  const previewSplitActive = selectedPreviews.length >= 2;

  // Bump when preview split layout changes so the network canvas refits/recenters.
  const networkViewportLayoutKey = useMemo(
    () => `${selectedPreviews.join(',')}:${previewSplitOrientation}:${selectedPreviews.length}`,
    [selectedPreviews, previewSplitOrientation],
  );

  // Render one preview pane body (header + content) that fills its flex cell.
  const renderPreviewPane = (type: PreviewType) => {
    if (type === 'network') {
      return (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <header className="relative z-10 flex shrink-0 items-center justify-between border-b bg-muted/40 px-4 py-2">
            <div className="flex items-center gap-2">
              <Share2 size={14} className="text-muted-foreground" />
              <h3 className="text-sm font-semibold">Network</h3>
            </div>
            <span className="text-xs text-muted-foreground">
              {classGraphNodes.length} classes · {displayInstances.length} individuals · {filteredRelations.length} relations
            </span>
          </header>
          <div className="relative min-h-0 flex-1 overflow-hidden">
            {/* View toggle — overlaid top-right of the canvas. Hidden entirely
                when there are too many individuals to draw legibly. */}
            {individualsViewAvailable && (
              <div className="absolute right-3 top-3 z-10 flex overflow-hidden rounded border bg-card/90 text-xs shadow backdrop-blur-sm">
                {(['classes', 'individuals'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setNetworkViewMode(mode)}
                    className={cn(
                      'px-2 py-1 capitalize',
                      networkViewMode === mode
                        ? 'bg-workspace-accent text-white'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            )}
            {graphNodes.length === 0 ? (
              <EmptyState
                icon={Filter}
                text="Run a search in the Individuals table to populate the network. Tick rows to highlight them."
              />
            ) : networkViewMode === 'individuals' ? (
              <VisNetwork
                nodes={graphNodes}
                edges={graphEdges}
                selectedNodeId={highlightedNodeUri}
                onNodeSelect={onSelectNode}
                onEdgeSelect={() => {}}
                physicsEnabled={true}
                stabilizeKey={stabilizeKey}
                circularNodes={true}
                viewportLayoutKey={networkViewportLayoutKey}
                fillContainer={previewSplitActive}
              />
            ) : (
              <VisNetwork
                nodes={classGraphNodes}
                edges={classGraphEdges}
                selectedNodeId={null}
                onNodeSelect={() => {}}
                onEdgeSelect={() => {}}
                physicsEnabled={true}
                stabilizeKey={stabilizeKey}
                viewportLayoutKey={networkViewportLayoutKey}
                fillContainer={previewSplitActive}
              />
            )}
          </div>
        </div>
      );
    }

    if (type === 'sparql') {
      return (
        <div className="min-h-0 flex-1 overflow-auto">
          <SparqlQueryPreview
            steps={sparqlSteps}
            graphUri={activeGraph?.uri ?? ''}
            collapsed={false}
            onToggle={() => {}}
            onRemoveStep={onRemoveStep}
          />
        </div>
      );
    }

    // type === 'table'
    if (type === 'table') return (
      <>
        <header className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
          <div className="flex items-center gap-2">
            <Braces size={14} className="text-muted-foreground" />
            <h3 className="text-sm font-semibold">Triples</h3>
            {allTriples.length > 0 && (
              <span className="text-xs text-muted-foreground">· {allTriples.length} triple{allTriples.length !== 1 ? 's' : ''}</span>
            )}
            {allTriples.length >= MAX_TRIPLES && (
              <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">
                capped at {MAX_TRIPLES.toLocaleString()}
              </span>
            )}
          </div>
          {allTriples.length > 0 && (
            <PreviewExportMenu triples={allTriples} workspaceId={workspaceId} />
          )}
        </header>
        <div className="min-h-0 flex-1 overflow-auto">
          <TriplesTable
            rows={pagedTriples}
            allRows={allTriples}
            columnFilters={tripleColumnFilters}
            onColumnFiltersChange={setTripleColumnFilters}
            sortState={tripleSortState}
            onSortStateChange={setTripleSortState}
            uniqueValues={tripleUniqueValues}
            loading={instancesLoading}
          />
        </div>
        {filteredTriples.length > 0 && (
          <TablePagination
            page={triplePage}
            pageSize={triplePageSize}
            total={filteredTriples.length}
            onPageChange={setTriplePage}
            onPageSizeChange={(s) => { setTriplePageSize(s); setTriplePage(0); }}
          />
        )}
      </>
    );

    // type === 'flat'
    if (type === 'flat') return (
      <>
        <header className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
          <div className="flex items-center gap-2">
            <LayoutList size={14} className="text-muted-foreground" />
            <h3 className="text-sm font-semibold">Table</h3>
            {allFlatTableRows.length > 0 && (
              <span className="text-xs text-muted-foreground">
                · {allFlatTableRows.length} row{allFlatTableRows.length !== 1 ? 's' : ''}
                {selectedInstanceUris.size > 0 && ` (${selectedInstanceUris.size} selected)`}
              </span>
            )}
          </div>
          {allFlatTableRows.length > 0 && (
            <button
              type="button"
              onClick={() => setCsvExportOpen(true)}
              className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs hover:bg-muted"
            >
              <Download size={12} />
              Export CSV
            </button>
          )}
        </header>
        <div className="min-h-0 flex-1 overflow-auto">
          <FlatInstancesTable
            columns={flatTableCols}
            rows={pagedFlatTableRows}
            allRows={allFlatTableRows}
            columnFilters={flatTableColumnFilters}
            onColumnFiltersChange={setFlatTableColumnFilters}
            sortState={flatTableSortState}
            onSortStateChange={setFlatTableSortState}
            uniqueValues={flatTableUniqueValues}
            loading={instancesLoading}
          />
        </div>
        {filteredFlatTableRows.length > 0 && (
          <TablePagination
            page={flatTablePage}
            pageSize={flatTablePageSize}
            total={filteredFlatTableRows.length}
            onPageChange={setFlatTablePage}
            onPageSizeChange={(s) => { setFlatTablePageSize(s); setFlatTablePage(0); }}
          />
        )}
      </>
    );

    return null;
  };

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left: filters + tables, hidden when preview is maximized */}
      <div className={cn('flex shrink-0 flex-col overflow-hidden border-r', previewSize === 'full' ? 'hidden' : 'w-[60%]')}>
        {/* Filter controls */}
        <div className="flex flex-col gap-2 border-b bg-card px-4 py-2">
          <div className="flex items-center gap-2 rounded-md border bg-background px-3 py-1.5">
            <Search size={14} className="text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search instances..."
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            {search && (
              <button onClick={() => onSearchChange('')}>
                <X size={14} className="text-muted-foreground hover:text-foreground" />
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <CheckboxFilter
                label="Graph"
                loading={graphsLoading}
                options={graphs.map((g) => ({ uri: g.uri, label: g.label, hint: g.role_label }))}
                selected={activeGraph ? [activeGraph.uri] : []}
                onToggle={(uri) => {
                  if (uri !== activeGraph?.uri) {
                    const g = graphs.find((gr) => gr.uri === uri);
                    if (g) onGraphChange(g);
                  }
                }}
                onSetSelected={(uris) => {
                  const newUri = uris.find((u) => u !== activeGraph?.uri) ?? uris[0];
                  if (newUri) {
                    const g = graphs.find((gr) => gr.uri === newUri);
                    if (g) onGraphChange(g);
                  }
                }}
                emptyMessage="No graphs available."
              />
            </div>
            <div className="flex-1">
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
          <div className="flex items-center gap-2">
            {savedViews.length > 0 && (
              <SavedViewsMenu
                views={savedViews}
                activeSavedViewId={activeSavedViewId}
                onApply={onApplyView}
                onDelete={onDeleteView}
              />
            )}
            <button
              onClick={() => {
                setTripleColumnFilters({});
                setTripleSortState(null);
                setTriplePage(0);
                setFlatTableColumnFilters({});
                setFlatTableSortState(null);
                setFlatTablePage(0);
                setInspectedInstance(null);
                setSelectedPreviews(['network']);
                setPreviewSplitOrientation('vertical');
                setPreviewSize('full');
                setNetworkViewMode('classes');
                setOpenSections(['instances', 'relations']);
                onClearAll();
              }}
              className="flex shrink-0 items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
              title="Reset all filters, selections, and previews to the initial view"
            >
              <X size={14} />
              Reset
            </button>
            <button
              onClick={onOpenSaveDialog}
              className="flex shrink-0 items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
              title="Save current filters as a view"
            >
              <Save size={14} />
              Save view
            </button>
          </div>
        </div>
          {/* Table 1: Instances */}
          <section className={cn('flex flex-col overflow-hidden border-b', instancesCollapsed ? 'shrink-0' : 'min-h-0 flex-1')}>
            <header className="flex h-10 items-center justify-between border-b bg-muted/40 px-4">
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
                {displayInstances.length > 0 && (
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                    {selectedInstanceUris.size > 0
                      ? `${selectedInstanceUris.size}/${displayInstances.length}`
                      : displayInstances.length}
                  </span>
                )}
              </button>
            </header>
            {!instancesCollapsed && selectedInstancesByClass.length > 0 && (
              <div className="flex flex-wrap gap-1 border-b bg-muted/20 px-3 py-1.5">
                {selectedInstancesByClass.map(({ label, count }) => (
                  <span
                    key={label}
                    className="inline-flex items-center rounded-full bg-workspace-accent/10 px-2 py-0.5 text-[11px] text-workspace-accent"
                  >
                    {label} ({count})
                  </span>
                ))}
              </div>
            )}
            {!instancesCollapsed && (
            <>
            <div className="min-h-0 flex-1 overflow-auto">
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
                  onToggle={handleToggleInstance}
                  onSetSelected={handleSetSelectedInstances}
                  onRowClick={(uri) => {
                    const inst = displayInstances.find((i) => i.uri === uri) ?? null;
                    setInspectedInstance(inst);
                  }}
                  columnFilters={columnFilters}
                  onColumnFiltersChange={onColumnFiltersChange}
                  sortState={sortState}
                  onSortStateChange={onSortStateChange}
                  instances={displayInstances}
                />
              )}
            </div>
            {displayInstances.length > 0 && (
              <TablePagination
                page={instancePage}
                pageSize={instancePageSize}
                total={displayInstances.length}
                onPageChange={setInstancePage}
                onPageSizeChange={(s) => { setInstancePageSize(s); setInstancePage(0); }}
              />
            )}
            </>
            )}
          </section>

          {/* Table 2: Relations */}
          <section className={cn('flex flex-col overflow-hidden border-t border-b', relationsCollapsed ? 'shrink-0' : 'min-h-0 flex-1')}>
            <header className="flex h-10 items-center gap-2 border-b bg-muted/40 px-4">
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
                {filteredRelations.length > 0 && (
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                    {selectedRelationRowKeys.size > 0
                      ? `${selectedRelationRowKeys.size}/${filteredRelations.length}`
                      : filteredRelations.length}
                  </span>
                )}
              </button>
            </header>
            {!relationsCollapsed && (
            <>
            <div className="min-h-0 flex-1 overflow-auto">
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
                  onToggleRow={handleToggleRelationRow}
                  onSetSelectedRows={handleSetSelectedRelationRows}
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
      </div>

      {/* Right panel: 3-state Preview drawer (full | middle | collapsed) */}
      {previewSize === 'collapsed' ? (
        <div className="flex w-8 shrink-0 flex-col items-center border-l bg-card pt-2">
          <button
            type="button"
            onClick={() => setPreviewSize('middle')}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Restore preview"
          >
            <ChevronLeft size={14} />
          </button>
          <span
            className="mt-3 text-[11px] font-medium text-muted-foreground"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
          >
            Preview
          </span>
        </div>
      ) : (
      <aside className="flex flex-1 min-w-0 flex-col overflow-hidden border-l bg-card">
          {inspectedInstance ? (
            <InstanceInspector
              instance={inspectedInstance}
              graphUri={activeGraph?.uri ?? ''}
              workspaceId={workspaceId}
              onClose={() => setInspectedInstance(null)}
            />
          ) : (
            <>
              <header className="flex h-10 items-center justify-between gap-2 border-b bg-muted/40 px-4">
                <div className="flex items-center gap-2">
                  <div className="flex items-center">
                    <button
                      type="button"
                      onClick={() => setPreviewSize((s) => s === 'full' ? 'middle' : 'full')}
                      className={cn('rounded-l p-1 hover:bg-muted hover:text-foreground', previewSize === 'full' ? 'text-foreground' : 'text-muted-foreground')}
                      title={previewSize === 'full' ? 'Restore to split' : 'Expand to full width'}
                    >
                      <ChevronLeft size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreviewSize((s) => s === 'full' ? 'middle' : 'collapsed')}
                      className="rounded-r p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title={previewSize === 'full' ? 'Restore to split' : 'Collapse preview'}
                    >
                      <ChevronRight size={14} />
                    </button>
                  </div>
                  <Eye size={14} className="text-muted-foreground" />
                  <h3 className="text-sm font-semibold">Preview</h3>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-3">
                    {PREVIEW_TYPE_DEFS.map(({ id, label, icon: Icon }) => {
                      const checked = selectedPreviews.includes(id);
                      const atMax = !checked && selectedPreviews.length >= 2;
                      return (
                        <label
                          key={id}
                          className={cn(
                            'flex items-center gap-1.5 text-xs',
                            atMax ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'
                          )}
                          title={
                            atMax
                              ? 'Up to two previews at a time'
                              : `${checked ? 'Hide' : 'Show'} ${label}`
                          }
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={atMax}
                            onChange={() => togglePreview(id)}
                            style={{ accentColor: 'var(--workspace-accent, #22c55e)' }}
                            className="h-3.5 w-3.5 cursor-pointer disabled:cursor-not-allowed"
                          />
                          <Icon size={14} className="text-muted-foreground" />
                          {label}
                        </label>
                      );
                    })}
                  </div>
                  {selectedPreviews.length === 2 && (
                    <div className="flex overflow-hidden rounded-md border text-xs">
                      <button
                        type="button"
                        onClick={() => setPreviewSplitOrientation('horizontal')}
                        className={cn(
                          'px-2 py-1',
                          previewSplitOrientation === 'horizontal'
                            ? 'bg-workspace-accent text-white'
                            : 'text-muted-foreground hover:bg-muted'
                        )}
                        title="Split side by side"
                      >
                        <Columns2 size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setPreviewSplitOrientation('vertical')}
                        className={cn(
                          'border-l px-2 py-1',
                          previewSplitOrientation === 'vertical'
                            ? 'bg-workspace-accent text-white'
                            : 'text-muted-foreground hover:bg-muted'
                        )}
                        title="Split stacked"
                      >
                        <Rows2 size={14} />
                      </button>
                    </div>
                  )}
                </div>
              </header>
              {selectedPreviews.length === 0 ? (
                <div className="flex min-h-0 flex-1 items-center justify-center p-6">
                  <EmptyState
                    icon={Eye}
                    text="Select Network, Sparql Query, Triples or Table above to show a preview."
                  />
                </div>
              ) : (
                <div
                  className={cn(
                    'flex min-h-0 flex-1',
                    selectedPreviews.length === 2 && previewSplitOrientation === 'vertical'
                      ? 'flex-col'
                      : 'flex-row'
                  )}
                >
                  {selectedPreviews.map((type, idx) => (
                    <div
                      key={type}
                      className={cn(
                        'flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden',
                        idx > 0 &&
                          (previewSplitOrientation === 'vertical' ? 'border-t' : 'border-l')
                      )}
                    >
                      {renderPreviewPane(type)}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </aside>
      )}

      {/* CSV export options dialog */}
      {csvExportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setCsvExportOpen(false)}>
          <div className="w-80 rounded-lg border bg-card p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="mb-4 text-sm font-semibold">Export CSV options</h3>

            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-muted-foreground">Encoding</label>
                <select
                  value={csvEncoding}
                  onChange={(e) => setCsvEncoding(e.target.value as 'utf-8' | 'utf-8-bom')}
                  className="rounded border bg-background px-2 py-1.5 text-xs"
                >
                  <option value="utf-8">UTF-8</option>
                  <option value="utf-8-bom">UTF-8 with BOM (Excel)</option>
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-muted-foreground">Column separator</label>
                <select
                  value={csvSeparator}
                  onChange={(e) => setCsvSeparator(e.target.value)}
                  className="rounded border bg-background px-2 py-1.5 text-xs"
                >
                  <option value=";">Semicolon ( ; )</option>
                  <option value=",">Comma ( , )</option>
                  <option value={'\t'}>Tab</option>
                  <option value="|">Pipe ( | )</option>
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-muted-foreground">Decimal separator</label>
                <select
                  value={csvDecimal}
                  onChange={(e) => setCsvDecimal(e.target.value)}
                  className="rounded border bg-background px-2 py-1.5 text-xs"
                >
                  <option value=",">Comma ( , )</option>
                  <option value=".">Period ( . )</option>
                </select>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCsvExportOpen(false)}
                className="rounded-md border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  exportFlatTableToCsv(filteredFlatTableRows, flatTableCols, {
                    encoding: csvEncoding,
                    separator: csvSeparator,
                    decimal: csvDecimal,
                  });
                  setCsvExportOpen(false);
                }}
                className="rounded-md bg-workspace-accent px-3 py-1.5 text-xs text-white hover:opacity-90"
              >
                Export
              </button>
            </div>
          </div>
        </div>
      )}
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

function exportFlatTableToCsv(
  rows: Record<string, string>[],
  columns: { id: string; label: string }[],
  options: { encoding: 'utf-8' | 'utf-8-bom'; separator: string; decimal: string } = {
    encoding: 'utf-8', separator: ';', decimal: ',',
  }
) {
  const { encoding, separator, decimal } = options;
  const applyDecimal = (v: string) =>
    decimal === '.' ? v : v.replace(/(?<=\d)\.(?=\d)/g, decimal);
  const escape = (v: string) => {
    const val = applyDecimal((v ?? '').replace(/"/g, '""'));
    return `"${val}"`;
  };
  const header = columns.map((c) => escape(c.label)).join(separator);
  const lines  = rows.map((row) => columns.map((c) => escape(row[c.id] ?? '')).join(separator));
  let content  = [header, ...lines].join('\n');
  if (encoding === 'utf-8-bom') content = '﻿' + content;
  downloadBlob(content, 'instances-table.csv', 'text/csv;charset=utf-8;');
}

const TRIPLE_EXPORT_FORMATS: { id: TripleExportFormat; label: string }[] = [
  { id: 'nt', label: 'N-Triples (.nt)' },
  { id: 'ttl', label: 'Turtle (.ttl)' },
  { id: 'owl', label: 'OWL (.owl)' },
];

function PreviewExportMenu({
  triples,
  workspaceId,
}: {
  triples: SparqlTriple[];
  workspaceId: string;
}) {
  const [open, setOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const handleExport = async (format: TripleExportFormat) => {
    setExporting(true);
    try {
      const res = await authFetch(`${getApiUrl()}/api/graph/discovery/triples-export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          triples: triples.map((t) => ({
            s: t.s,
            p: t.p,
            o: t.o,
            is_literal: t.isLiteral,
          })),
          format,
        }),
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const data = (await res.json()) as {
        content: string;
        filename: string;
        media_type: string;
      };
      downloadBlob(data.content, data.filename, data.media_type);
    } catch {
      const { content, filename, mime } = serializeTriples(triples, format);
      downloadBlob(content, filename, mime);
    } finally {
      setExporting(false);
      setOpen(false);
    }
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        disabled={triples.length === 0 || exporting}
        className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        title="Export all triples (rdflib, grouped by subject URI)"
      >
        {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
        Export
        <ChevronDown size={11} />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-40 rounded-md border bg-background py-1 shadow-lg">
          {TRIPLE_EXPORT_FORMATS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => handleExport(id)}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-muted"
            >
              {label}
            </button>
          ))}
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
                <th className="border-b px-3 py-1.5 text-left font-medium">BFO Bucket</th>
              </tr>
            </thead>
            <tbody>
              {instances.map((inst) => (
                <tr key={inst.uri} className="border-b hover:bg-muted/50">
                  <td className="max-w-[260px] truncate px-3 py-1.5 font-mono text-[11px]" title={inst.uri}>{inst.uri}</td>
                  <td className="max-w-[200px] truncate px-3 py-1.5" title={inst.label}>{inst.label}</td>
                  <td className="max-w-[200px] truncate px-3 py-1.5" title={inst.class_uri}>{inst.class_label || compactUri(inst.class_uri)}</td>
                  <td className="max-w-[200px] px-3 py-1.5"><BfoBucketBadge uri={inst.bfo_bucket_uri} label={inst.bfo_bucket_label} /></td>
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

function TriplesTable({
  rows,
  allRows,
  columnFilters,
  onColumnFiltersChange,
  sortState,
  onSortStateChange,
  uniqueValues,
  loading = false,
}: {
  rows: SparqlTriple[];
  allRows: SparqlTriple[];
  columnFilters: Record<string, ColumnFilter>;
  onColumnFiltersChange: (
    updater:
      | Record<string, ColumnFilter>
      | ((prev: Record<string, ColumnFilter>) => Record<string, ColumnFilter>)
  ) => void;
  sortState: SortState | null;
  onSortStateChange: (s: SortState | null) => void;
  uniqueValues: { s: string[]; p: string[]; o: string[] };
  loading?: boolean;
}) {
  const cols = [
    { id: 's', label: 's (subject)' },
    { id: 'p', label: 'p (predicate)' },
    { id: 'o', label: 'o (object)' },
  ];

  const displayRows = useMemo(() => {
    const copy = [...rows];
    if (!sortState) {
      copy.sort(
        (a, b) =>
          a.s.localeCompare(b.s) || a.p.localeCompare(b.p) || a.o.localeCompare(b.o),
      );
    }
    return copy;
  }, [rows, sortState]);

  if (loading) {
    return <EmptyState icon={Loader2} text="Loading triples..." spinning />;
  }

  if (allRows.length === 0) {
    return (
      <EmptyState
        icon={LayoutList}
        text="No triples available. Select a graph with individuals to explore."
      />
    );
  }

  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 z-10 bg-muted">
        <tr>
          {cols.map((col) => (
            <ColumnHeader
              key={col.id}
              column={col}
              uniqueValues={uniqueValues[col.id as 's' | 'p' | 'o']}
              sortState={sortState}
              onSortStateChange={onSortStateChange}
              columnFilters={columnFilters}
              onColumnFiltersChange={onColumnFiltersChange}
            />
          ))}
        </tr>
      </thead>
      <tbody>
        {displayRows.map((t, idx) => {
          const isNewSubject = idx === 0 || t.s !== displayRows[idx - 1].s;
          return (
          <tr
            key={`${t.s}|${t.p}|${t.o}|${idx}`}
            className={cn(
              'border-b hover:bg-muted/50',
              isNewSubject && idx > 0 && 'border-t-2 border-t-border',
            )}
          >
            <td
              className={cn(
                'max-w-[260px] truncate px-3 py-1.5 font-mono text-[11px]',
                !isNewSubject && 'text-muted-foreground/40',
              )}
              title={t.s}
            >
              {isNewSubject ? compactUri(t.s) : '↳'}
            </td>
            <td className="max-w-[200px] truncate px-3 py-1.5 font-mono text-[11px]" title={t.p}>
              {compactUri(t.p)}
            </td>
            <td
              className={cn(
                'max-w-[260px] truncate px-3 py-1.5',
                t.isLiteral
                  ? 'text-green-700 dark:text-green-400'
                  : 'font-mono text-[11px]'
              )}
              title={t.o}
            >
              {t.isLiteral ? `"${t.o}"` : compactUri(t.o)}
            </td>
          </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Flat instances table ──────────────────────────────────────────────────────

const isUriCol = (id: string) => id === 'class_uri' || id.startsWith('rel__');

function FlatInstancesTable({
  columns,
  rows,
  allRows,
  columnFilters,
  onColumnFiltersChange,
  sortState,
  onSortStateChange,
  uniqueValues,
  loading = false,
}: {
  columns: { id: string; label: string }[];
  rows: Record<string, string>[];
  allRows: Record<string, string>[];
  columnFilters: Record<string, ColumnFilter>;
  onColumnFiltersChange: (
    updater:
      | Record<string, ColumnFilter>
      | ((prev: Record<string, ColumnFilter>) => Record<string, ColumnFilter>)
  ) => void;
  sortState: SortState | null;
  onSortStateChange: (s: SortState | null) => void;
  uniqueValues: Record<string, string[]>;
  loading?: boolean;
}) {
  if (loading) {
    return <EmptyState icon={Loader2} text="Loading..." spinning />;
  }
  if (allRows.length === 0) {
    return (
      <EmptyState
        icon={LayoutList}
        text="Select individuals or relations to populate this table."
      />
    );
  }

  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 z-10 bg-muted">
        <tr>
          {columns.map((col) => (
            <ColumnHeader
              key={col.id}
              column={col}
              uniqueValues={uniqueValues[col.id] ?? []}
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
              colSpan={columns.length}
              className="px-4 py-6 text-center text-xs text-muted-foreground"
            >
              No rows match the current filters.
            </td>
          </tr>
        )}
        {rows.map((row, idx) => (
          <tr key={idx} className="border-b hover:bg-muted/50">
            {columns.map((col) => {
              const value = row[col.id] ?? '';
              const isMono = isUriCol(col.id);
              return (
                <td
                  key={col.id}
                  className={cn(
                    'max-w-[240px] truncate px-3 py-1.5',
                    isMono ? 'font-mono text-[11px]' : 'text-xs',
                  )}
                  title={col.id === 'class_uri' ? (row._class_uri_full ?? value) : value}
                >
                  {value}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
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
    <div className="flex flex-1 flex-col overflow-hidden">
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
    </div>
  );
}

// ── Tables ───────────────────────────────────────────────────────────────────

function BfoBucketBadge({ uri, label }: { uri?: string; label?: string }) {
  const bucket = getBfoBucket(uri);
  if (!bucket && !label) return <span className="text-muted-foreground">—</span>;
  const color = bucket?.color ?? '#9ca3af';
  const shortLabel = bucket?.label ?? label ?? '—';
  const typeName = bucket?.type ?? label ?? '';
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-semibold text-white"
        style={{ backgroundColor: color }}
      >
        {shortLabel}
      </span>
      <span className="truncate text-xs text-muted-foreground">{typeName}</span>
    </span>
  );
}

function getInstanceColumnValue(
  inst: ApiDiscoveryInstance,
  columnId: string
): string {
  if (columnId === 'uri') return inst.uri;
  if (columnId === 'class') return inst.class_label || compactUri(inst.class_uri);
  if (columnId === 'bfo_bucket') return inst.bfo_bucket_label || compactUri(inst.bfo_bucket_uri || '') || '';
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
  const allSelectedCount = instances.reduce(
    (acc, r) => (selectedUris.has(r.uri) ? acc + 1 : acc),
    0
  );
  const allSelected = instances.length > 0 && allSelectedCount === instances.length;
  const noneSelected = allSelectedCount === 0;
  const indeterminate = !allSelected && !noneSelected;

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  const handleToggleAll = () => {
    if (allSelected) {
      onSetSelected(new Set());
    } else {
      onSetSelected(new Set(instances.map((r) => r.uri)));
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
              checked={allSelected}
              onChange={handleToggleAll}
              disabled={instances.length === 0}
              className="h-3.5 w-3.5"
              title={allSelected ? 'Deselect all rows' : 'Select all rows'}
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
                    ) : col.id === 'bfo_bucket' ? (
                      <BfoBucketBadge uri={inst.bfo_bucket_uri} label={inst.bfo_bucket_label} />
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
    included: new Set<string>(),
  };

  const isSorted = sortState?.column === column.id;
  const sortDir = isSorted ? sortState!.direction : null;

  const updateFilter = (next: Partial<ColumnFilter>) => {
    onColumnFiltersChange((prev) => ({
      ...prev,
      [column.id]: {
        search: next.search ?? filter.search,
        included: next.included ?? filter.included,
      },
    }));
  };

  const toggleSort = () => {
    if (!isSorted) onSortStateChange({ column: column.id, direction: 'asc' });
    else if (sortDir === 'asc')
      onSortStateChange({ column: column.id, direction: 'desc' });
    else onSortStateChange(null);
  };

  const hasFilter = filter.search.length > 0 || filter.included.size > 0;

  const displayedValues = useMemo(() => {
    const t = filter.search.trim().toLowerCase();
    if (!t) return uniqueValues;
    return uniqueValues.filter((v) => v.toLowerCase().includes(t));
  }, [uniqueValues, filter.search]);

  const checkedCount = displayedValues.filter((v) => filter.included.has(v)).length;
  const allChecked = displayedValues.length > 0 && checkedCount === displayedValues.length;
  const noneChecked = checkedCount === 0;
  const indeterminate = !allChecked && !noneChecked;

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  const handleSelectAll = () => {
    const next = new Set(filter.included);
    if (allChecked) {
      for (const v of displayedValues) next.delete(v);
    } else {
      for (const v of displayedValues) next.add(v);
    }
    updateFilter({ included: next });
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
                const checked = filter.included.has(v);
                return (
                  <label
                    key={v}
                    className="flex cursor-pointer items-center gap-2 px-3 py-1 text-xs hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        const next = new Set(filter.included);
                        if (checked) next.delete(v);
                        else next.add(v);
                        updateFilter({ included: next });
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
        className="flex w-full items-center justify-between rounded-md border bg-background px-3 py-1.5 text-left text-sm text-muted-foreground hover:bg-muted/50"
      >
        <span>{label}</span>
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
