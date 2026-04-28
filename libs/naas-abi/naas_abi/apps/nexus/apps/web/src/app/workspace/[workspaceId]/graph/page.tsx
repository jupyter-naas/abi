'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Header } from '@/components/shell/header';
import {
  Database,
  Filter,
  Search,
  Eye,
  Network,
  Code,
  Table,
  Play,
  Save,
  Trash2,
  Box,
  Link2,
  Circle,
  RefreshCw,
  X,
  Share2,
  Workflow,
  Loader2,
  UserPlus,
  ChevronDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import {
  useKnowledgeGraphStore,
  type GraphViewType,
  type GraphTripleFilter,
  type GraphView,
} from '@/stores/knowledge-graph';
import { authFetch } from '@/stores/auth';

// Dynamically import vis-network to avoid SSR issues
const VisNetwork = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.VisNetwork),
  { ssr: false, loading: () => <div className="flex h-full items-center justify-center"><span className="text-muted-foreground">Loading graph...</span></div> }
);

const BFOLegend = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.BFOLegend),
  { ssr: false }
);

// Types for graph data from API
interface ApiNode {
  id: string;
  workspace_id: string;
  type: string;
  label: string;
  properties: Record<string, unknown>;
}

interface ApiEdge {
  id: string;
  workspace_id: string;
  source_id: string;
  target_id: string;
  source_label?: string;
  target_label?: string;
  type: string;
  properties?: Record<string, unknown>;
}

// Types for vis-network (adapted for visualization)
interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  sourceLabel?: string;
  targetLabel?: string;
  type: string;
  label?: string;
  properties?: Record<string, unknown>;
}

const GRAPH_VIEW_TYPES: { id: GraphViewType; label: string; icon: React.ElementType }[] = [
  { id: 'entities', label: 'Network', icon: Network },
  { id: 'overview', label: 'Metrics', icon: Eye },
  { id: 'table', label: 'Table', icon: Table },
];

const LEGACY_VIEW_MAP: Record<string, GraphViewType> = {
  visual: 'entities',
  schema: 'overview',
  statistics: 'overview',
};

function isSystemGraph(option: GraphOption): boolean {
  const id = option.id.trim().toLowerCase();
  const name = option.name.trim().toLowerCase();
  return (
    id === 'schema' ||
    id === 'nexus' ||
    id.endsWith('/schema') ||
    id.endsWith('/nexus') ||
    name === 'schema' ||
    name === 'nexus'
  );
}

const isGraphViewType = (value: string): value is GraphViewType =>
  GRAPH_VIEW_TYPES.some((view) => view.id === value);

type GraphPageMode = 'graph' | 'create-individual' | 'create-view' | 'create-graph' | 'sparql';

interface OntologyClassOption {
  id: string;
  name: string;
  description: string;
}

interface GraphOption {
  id: string;
  name: string;
}

interface FilterOption {
  uri: string;
  label: string;
}

interface FilterOptionsResponse {
  subjects: FilterOption[];
  predicates: FilterOption[];
  objects: FilterOption[];
}

interface TriplePreviewRow {
  subject: string;
  predicate: string;
  object: string;
}

interface TriplePreviewResponse {
  count: number;
  individual_count: number;
  object_properties_count: number;
  data_properties_count: number;
  rows: TriplePreviewRow[];
}

interface ApiOverview {
  kpis: {
    total_instances: number;
    total_relationships: number;
    average_degree: number;
    density: number;
  };
  instances_by_class: Array<{
    type: string;
    count: number;
  }>;
}

interface ViewFilterDraft {
  subject_uri: string;
  predicate_uri: string;
  object_uri: string;
}

function FilterOptionDropdown({
  options,
  value,
  onChange,
  placeholder,
}: {
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
        setSearchQuery('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    const t = searchQuery.trim().toLowerCase();
    const list = !t
      ? options
      : options.filter(
          (o) => o.label.toLowerCase().includes(t) || o.uri.toLowerCase().includes(t)
        );
    if (value && !list.some((o) => o.uri === value)) {
      const sel = options.find((o) => o.uri === value);
      if (sel) return [sel, ...list];
    }
    return list;
  }, [options, searchQuery, value]);

  const selected = options.find((o) => o.uri === value);
  const displayLabel = selected ? selected.label : '';

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary',
          'hover:bg-muted/50'
        )}
      >
        <span className={cn('truncate', !value && 'text-muted-foreground')}>
          {displayLabel || placeholder}
        </span>
        <ChevronDown size={14} className={cn('shrink-0 text-muted-foreground', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-full min-w-[16rem] max-h-64 overflow-hidden rounded-lg border bg-background shadow-lg">
          <div className="sticky top-0 border-b bg-background p-2">
            <input
              type="text"
              placeholder={`Search ${placeholder.toLowerCase()}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              autoFocus
            />
          </div>
          <div className="max-h-48 overflow-y-auto py-1">
            <button
              type="button"
              onClick={() => {
                onChange('');
                setOpen(false);
                setSearchQuery('');
              }}
              className={cn(
                'flex w-full items-center px-3 py-2 text-left text-sm',
                'hover:bg-muted',
                !value && 'bg-muted'
              )}
            >
              <span className="text-muted-foreground">{placeholder}</span>
            </button>
            {filtered.map((option) => (
              <button
                key={option.uri}
                type="button"
                onClick={() => {
                  onChange(option.uri);
                  setOpen(false);
                  setSearchQuery('');
                }}
                className={cn(
                  'flex w-full items-center px-3 py-2 text-left text-sm',
                  'hover:bg-muted',
                  value === option.uri && 'bg-muted'
                )}
              >
                <span className="truncate">{option.label}</span>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                No matches for &quot;{searchQuery}&quot;
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ClassOptionDropdown({
  options,
  value,
  onChange,
  placeholder,
  disabled = false,
}: {
  options: OntologyClassOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
        setSearchQuery('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    const t = searchQuery.trim().toLowerCase();
    if (!t) return options;
    return options.filter(
      (option) =>
        option.name.toLowerCase().includes(t) ||
        option.description.toLowerCase().includes(t)
    );
  }, [options, searchQuery]);

  const selected = options.find((option) => option.id === value);
  const selectedDisplay = selected
    ? selected.description
      ? `${selected.name}: ${selected.description}`
      : selected.name
    : '';

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen((prev) => !prev)}
        disabled={disabled}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border bg-background px-3 py-2 text-left text-sm outline-none focus:ring-2 focus:ring-primary',
          'hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-60'
        )}
      >
        <span className={cn('line-clamp-2 break-words', !value && 'text-muted-foreground')}>
          {selectedDisplay || placeholder}
        </span>
        <ChevronDown size={14} className={cn('shrink-0 text-muted-foreground', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-full max-h-64 overflow-hidden rounded-lg border bg-background shadow-lg">
          <div className="sticky top-0 border-b bg-background p-2">
            <input
              type="text"
              placeholder="Search class..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              autoFocus
            />
          </div>
          <div className="max-h-48 overflow-y-auto py-1">
            <button
              type="button"
              onClick={() => {
                onChange('');
                setOpen(false);
                setSearchQuery('');
              }}
              className={cn('w-full px-3 py-2 text-left text-sm hover:bg-muted', !value && 'bg-muted')}
            >
              <span className="text-muted-foreground">{placeholder}</span>
            </button>
            {filtered.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => {
                  onChange(option.id);
                  setOpen(false);
                  setSearchQuery('');
                }}
                className={cn(
                  'w-full px-3 py-2 text-left text-sm hover:bg-muted',
                  value === option.id && 'bg-muted'
                )}
              >
                <span className="block break-words">
                  {option.name}
                  {option.description ? `: ${option.description}` : ''}
                </span>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                No matches for &quot;{searchQuery}&quot;
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

interface GraphViewInfo {
  workspace_id: string;
  id: string;
  label: string;
  graph_names: string[];
  graph_filters: string[];
  scope: 'workspace' | 'user';
  user_id?: string | null;
  created_at?: string;
}

const GRAPH_CACHE_TTL_MS = 10 * 60 * 1000;
const GRAPH_CACHE_REFRESH_EVENT = 'graph-cache-refresh';

type TimestampedCacheEntry<T> = {
  data: T;
  expiresAt: number;
};

const networkCache = new Map<string, TimestampedCacheEntry<{ nodes: GraphNode[]; edges: GraphEdge[] }>>();
const overviewCache = new Map<string, TimestampedCacheEntry<ApiOverview | null>>();
const graphListCache = new Map<
  string,
  TimestampedCacheEntry<{
    graphOptions: GraphOption[];
    normalized: Array<{ id: string; label?: string }>;
    defaultGraphName: string;
  }>
>();

function readFreshCache<T>(cache: Map<string, TimestampedCacheEntry<T>>, key: string): T | undefined {
  const hit = cache.get(key);
  if (!hit) return undefined;
  if (Date.now() > hit.expiresAt) {
    cache.delete(key);
    return undefined;
  }
  return hit.data;
}

function writeCache<T>(cache: Map<string, TimestampedCacheEntry<T>>, key: string, data: T): void {
  cache.set(key, { data, expiresAt: Date.now() + GRAPH_CACHE_TTL_MS });
}

function clearGraphPageCaches(): void {
  networkCache.clear();
  overviewCache.clear();
  graphListCache.clear();
}

export default function GraphPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  
  // Local state for graph data from API (not persisted to localStorage)
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<ApiOverview | null>(null);
  
  // UI state
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const {
    activeViewType,
    setActiveViewType,
    selectedGraphId,
    visibleGraphIds,
    selectGraph,
    setVisibleGraphs,
    views,
    activeSavedViewId,
    setActiveSavedView,
    setViews,
  } = useKnowledgeGraphStore();
  const [zoomLevel, setZoomLevel] = useState(1);
  const [currentQuery, setCurrentQuery] = useState('');
  const [queryResults, setQueryResults] = useState<Record<string, string>[] | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [editorHeight, setEditorHeight] = useState(200);
  const [isResizing, setIsResizing] = useState(false);
  const [pageMode, setPageMode] = useState<GraphPageMode>('graph');
  const [individualLabel, setIndividualLabel] = useState('');
  const [selectedClassId, setSelectedClassId] = useState('');
  const [availableClasses, setAvailableClasses] = useState<OntologyClassOption[]>([]);
  const [classesLoading, setClassesLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creatingIndividual, setCreatingIndividual] = useState(false);
  const [selectedIndividualGraphId, setSelectedIndividualGraphId] = useState('');
  const [viewName, setViewName] = useState('');
  const [graphOptions, setGraphOptions] = useState<GraphOption[]>([]);
  const [selectedViewGraphIds, setSelectedViewGraphIds] = useState<string[]>([]);
  const [viewFilters, setViewFilters] = useState<ViewFilterDraft[]>([
    { subject_uri: '', predicate_uri: '', object_uri: '' },
  ]);
  const [viewFilterOptions, setViewFilterOptions] = useState<FilterOptionsResponse[]>([]);
  const [triplePreview, setTriplePreview] = useState<TriplePreviewResponse>({
    count: 0,
    individual_count: 0,
    object_properties_count: 0,
    data_properties_count: 0,
    rows: [],
  });
  const [previewLoading, setPreviewLoading] = useState(false);
  const [viewFormError, setViewFormError] = useState<string | null>(null);
  const [viewDescription, setViewDescription] = useState('');
  const [editingViewId, setEditingViewId] = useState<string | null>(null);
  const [graphName, setGraphName] = useState('');
  const [graphDescription, setGraphDescription] = useState('');
  const [graphFormError, setGraphFormError] = useState<string | null>(null);
  const [creatingGraph, setCreatingGraph] = useState(false);
  const loadRequestIdRef = useRef(0);
  const overviewRequestIdRef = useRef(0);
  const viewFilterOptionsRequestIdRef = useRef(0);
  const viewPreviewRequestIdRef = useRef(0);
  const activeSavedView = useMemo(
    () => views.find((view) => view.id === activeSavedViewId) ?? null,
    [views, activeSavedViewId]
  );
  const editingView = useMemo(
    () => (editingViewId ? views.find((view) => view.id === editingViewId) ?? null : null),
    [views, editingViewId]
  );
  const individualGraphOptions = useMemo(
    () => graphOptions.filter((option) => !isSystemGraph(option)),
    [graphOptions]
  );

  // Load graphs from API - fetches all visible graphs and merges them
  const loadFromApi = useCallback(async (options?: { force?: boolean }) => {
    const forceRefresh = options?.force === true;
    const requestId = ++loadRequestIdRef.current;
    setLoading(true);
    setError(null);

    try {
      const apiUrl = getApiUrl();
      const allNodes: GraphNode[] = [];
      const allEdges: GraphEdge[] = [];
      let defaultGraphName = '';
      let normalized: { id: string; label?: string }[] = [];

      try {
        const listCacheKey = `graph-list:${workspaceId}`;
        const cachedGraphList = !forceRefresh ? readFreshCache(graphListCache, listCacheKey) : undefined;
        if (cachedGraphList) {
          normalized = cachedGraphList.normalized;
          defaultGraphName = cachedGraphList.defaultGraphName;
          setGraphOptions(cachedGraphList.graphOptions);
        } else {
          const namesRes = await authFetch(
            `${apiUrl}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`
          );

          if (!namesRes.ok) {
            setGraphOptions([]);
          } else {
            const namesData = await namesRes.json();
            const graphs = Array.isArray(namesData)
              ? namesData
              : Array.isArray(namesData?.graphs)
                ? namesData.graphs
                : [];

            // Proper type guard: id AND label must be string
            normalized = graphs.filter(
              (g: unknown): g is { id: string; label: string } =>
                typeof g === "object" &&
                g !== null &&
                "id" in g &&
                "label" in g &&
                typeof (g as any).id === "string" &&
                typeof (g as any).label === "string"
            );

            if (normalized.length === 0) {
              setGraphOptions([]);
            } else {
              defaultGraphName = normalized[0].id;
              const optionsToCache = normalized.map((g: { id: string; label?: string }) => ({
                id: g.id,
                name: g.label ?? g.id,
              }));
              setGraphOptions(optionsToCache);
              writeCache(graphListCache, listCacheKey, {
                graphOptions: optionsToCache,
                normalized,
                defaultGraphName,
              });
            }
          }
        }
      } catch {
        setGraphOptions([]);
      }

      // Determine fetch strategy: use view endpoint when view selected; otherwise fetch selected graph.
      type NetworkRequest = { url: string; init?: RequestInit };
      let requestsToFetch: NetworkRequest[];

      if (activeSavedView) {
        const params = new URLSearchParams({
          workspace_id: workspaceId,
          limit: '500',
        });
        requestsToFetch = [
          {
            url: `${apiUrl}/api/view/${encodeURIComponent(activeSavedView.id)}/network?${params.toString()}`,
          },
        ];
      } else {
        const graphIdsToFetch =
          selectedGraphId
            ? [selectedGraphId]
            : visibleGraphIds.length > 0
            ? visibleGraphIds.filter((id: string) => !id.includes('#layer='))
            : normalized.map((graph) => graph.id);
        const effectiveGraphId = graphIdsToFetch[0] ?? defaultGraphName ?? '';
        const params = new URLSearchParams({
          workspace_id: workspaceId,
          limit: '500',
        });
        requestsToFetch = effectiveGraphId
          ? [{ url: `${apiUrl}/api/graph/${encodeURIComponent(effectiveGraphId)}/network?${params.toString()}` }]
          : [];
      }

      const networkCacheKey = `network:${requestsToFetch.map(({ url }) => url).join('||')}`;
      const cachedNetwork = !forceRefresh ? readFreshCache(networkCache, networkCacheKey) : undefined;
      if (cachedNetwork) {
        if (requestId === loadRequestIdRef.current) {
          setNodes(cachedNetwork.nodes);
          setEdges(cachedNetwork.edges);
        }
        return;
      }

      const responses = await Promise.all(
        requestsToFetch.map(({ url, init }) =>
          authFetch(url, init)
            .then((res) => (res.ok ? res.json() : { nodes: [], edges: [] }))
            .catch(() => ({ nodes: [], edges: [] }))
        )
      );
      
      // Merge all graph data
      responses.forEach((data) => {
        if (data.nodes) {
          const visNodes: GraphNode[] = data.nodes.map((node: ApiNode) => ({
            id: node.id,
            label: node.label,
            type: node.type,
            properties: node.properties || {},
            x: node.properties?.x as number | undefined,
            y: node.properties?.y as number | undefined,
          }));
          allNodes.push(...visNodes);
        }
        
        if (data.edges) {
          const visEdges: GraphEdge[] = data.edges.map((edge: ApiEdge) => ({
            id: edge.id,
            source: edge.source_id,
            target: edge.target_id,
            sourceLabel: edge.source_label,
            targetLabel: edge.target_label,
            type: edge.type,
            label: edge.type,
            properties: edge.properties || {},
          }));
          allEdges.push(...visEdges);
        }
      });
      
      // Deduplicate nodes and edges by ID
      const uniqueNodes = Array.from(new Map(allNodes.map((n) => [n.id, n])).values());
      const uniqueEdges = Array.from(new Map(allEdges.map((e) => [e.id, e])).values());

      if (requestId !== loadRequestIdRef.current) {
        return;
      }

      setNodes(uniqueNodes);
      setEdges(uniqueEdges);
      writeCache(networkCache, networkCacheKey, { nodes: uniqueNodes, edges: uniqueEdges });
    } catch (err) {
      if (requestId !== loadRequestIdRef.current) {
        return;
      }
      console.error('Failed to load graph from API:', err);
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      if (requestId === loadRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [workspaceId, selectedGraphId, visibleGraphIds, activeSavedView]);

  const loadOverviewFromApi = useCallback(async (options?: { force?: boolean }) => {
    const forceRefresh = options?.force === true;
    if (pageMode !== 'graph' || activeViewType !== 'overview') {
      return;
    }

    const requestId = ++overviewRequestIdRef.current;
    const apiUrl = getApiUrl();
    let overviewUrl: string | null = null;

    if (activeSavedView) {
      overviewUrl = `${apiUrl}/api/view/${encodeURIComponent(activeSavedView.id)}/overview?workspace_id=${encodeURIComponent(workspaceId)}`;
    } else {
      const graphIdsToFetch =
        selectedGraphId
          ? [selectedGraphId]
          : visibleGraphIds.length > 0
          ? visibleGraphIds.filter((id: string) => !id.includes('#layer='))
          : graphOptions.map((graph) => graph.id);
      const effectiveGraphId = graphIdsToFetch[0] ?? '';
      if (effectiveGraphId) {
        overviewUrl = `${apiUrl}/api/graph/${encodeURIComponent(effectiveGraphId)}/overview?workspace_id=${encodeURIComponent(workspaceId)}`;
      }
    }

    if (!overviewUrl) {
      if (requestId === overviewRequestIdRef.current) {
        setOverview(null);
      }
      return;
    }

    const overviewCacheKey = `overview:${overviewUrl}`;
    const cachedOverview = !forceRefresh ? readFreshCache(overviewCache, overviewCacheKey) : undefined;
    if (cachedOverview !== undefined) {
      if (requestId === overviewRequestIdRef.current) {
        setOverview(cachedOverview);
      }
      return;
    }

    try {
      const response = await authFetch(overviewUrl);
      const data = response.ok ? await response.json() : null;
      if (requestId === overviewRequestIdRef.current) {
        setOverview(data as ApiOverview | null);
        writeCache(overviewCache, overviewCacheKey, data as ApiOverview | null);
      }
    } catch {
      if (requestId === overviewRequestIdRef.current) {
        setOverview(null);
      }
    }
  }, [
    activeSavedView,
    activeViewType,
    graphOptions,
    pageMode,
    selectedGraphId,
    visibleGraphIds,
    workspaceId,
  ]);

  const loadViewsFromApi = useCallback(async () => {
    const apiUrl = getApiUrl();
    const response = await authFetch(
      `${apiUrl}/api/view/list?workspace_id=${encodeURIComponent(workspaceId)}`
    );
    if (!response.ok) {
      throw new Error(`Failed to load views: ${response.status}`);
    }
    const data: unknown = await response.json();
    const apiViews: GraphViewInfo[] = Array.isArray(data) ? (data as GraphViewInfo[]) : [];
    const normalizedViews: GraphView[] = apiViews.map((view) => ({
      id: view.id,
      name: view.label || view.id,
      scope: view.scope,
      userId: view.user_id ?? undefined,
      type: 'entities',
      graphIds: Array.isArray(view.graph_names) ? view.graph_names : [],
      filters: Array.isArray(view.graph_filters)
        ? view.graph_filters.map(
            (uri) =>
              ({
                subject_uri: '',
                predicate_uri: '',
                object_uri: '',
                uri,
              }) as GraphTripleFilter
          )
        : [],
      createdAt: view.created_at ? new Date(view.created_at) : new Date(),
    }));
    setViews(normalizedViews);
  }, [workspaceId, setViews]);

  // Load on mount and when workspace or visible graphs change
  useEffect(() => {
    loadFromApi();
  }, [loadFromApi]);

  useEffect(() => {
    if (pageMode !== 'graph' || activeViewType !== 'overview') {
      setOverview(null);
      return;
    }
    loadOverviewFromApi();
  }, [activeViewType, loadOverviewFromApi, pageMode]);

  useEffect(() => {
    const onGraphCacheRefresh = () => {
      clearGraphPageCaches();
      void loadFromApi({ force: true });
      if (pageMode === 'graph' && activeViewType === 'overview') {
        void loadOverviewFromApi({ force: true });
      } else {
        setOverview(null);
      }
    };
    window.addEventListener(GRAPH_CACHE_REFRESH_EVENT, onGraphCacheRefresh);
    return () => window.removeEventListener(GRAPH_CACHE_REFRESH_EVENT, onGraphCacheRefresh);
  }, [activeViewType, loadFromApi, loadOverviewFromApi, pageMode]);

  useEffect(() => {
    loadViewsFromApi().catch((err) => {
      console.error('Failed to load graph views:', err);
    });
  }, [loadViewsFromApi]);

  useEffect(() => {
    const requestedView = searchParams.get('view');
    if (requestedView === 'new-view') {
      setEditingViewId(null);
      setPageMode('create-view');
      return;
    }
    if (requestedView === 'edit-view') {
      const viewId = searchParams.get('view_id');
      setEditingViewId(viewId);
      setPageMode('create-view');
      return;
    }
    if (requestedView === 'create-individual') {
      setEditingViewId(null);
      setPageMode('create-individual');
      return;
    }
    if (requestedView === 'sparql') {
      setEditingViewId(null);
      setPageMode('sparql');
      return;
    }
    if (requestedView === 'create-graph') {
      setEditingViewId(null);
      setPageMode('create-graph');
      return;
    }
    setEditingViewId(null);
    setPageMode('graph');
    if (requestedView) {
      const normalizedView = LEGACY_VIEW_MAP[requestedView] || requestedView;
      if (isGraphViewType(normalizedView)) {
        setActiveViewType(normalizedView);
      }
    }
  }, [searchParams, setActiveViewType]);

  useEffect(() => {
    if (pageMode === 'graph' && activeViewType === 'sparql') {
      setActiveViewType('entities');
    }
  }, [pageMode, activeViewType, setActiveViewType]);

  const loadOntologyClasses = useCallback(async () => {
    setClassesLoading(true);
    try {
      const apiUrl = getApiUrl();
      const response = await authFetch(`${apiUrl}/api/ontology/classes`);
      if (!response.ok) {
        throw new Error(`Failed to fetch classes: ${response.status}`);
      }

      const data = await response.json();
      const sourceItems = Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || [];
      const normalizedClasses = sourceItems
        .map((item) => {
          const typedItem = item as {
            id?: string;
            iri?: string;
            name?: string;
            label?: string;
            description?: string;
            definition?: string;
          };
          const id = typedItem.id || typedItem.iri || '';
          const name = typedItem.name || typedItem.label || typedItem.iri || '';
          const description = typedItem.description || typedItem.definition || '';
          if (!id || !name) {
            return null;
          }
          return { id, name, description };
        })
        .filter((item): item is OntologyClassOption => item !== null)
        .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
      setAvailableClasses(normalizedClasses);
    } catch (err) {
      console.error('Failed to fetch ontology classes:', err);
      setAvailableClasses([]);
    } finally {
      setClassesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (pageMode === 'create-individual') {
      loadOntologyClasses();
    }
  }, [pageMode, loadOntologyClasses]);

  useEffect(() => {
    if (pageMode !== 'create-individual') {
      return;
    }

    if (individualGraphOptions.length === 0) {
      if (selectedIndividualGraphId) {
        setSelectedIndividualGraphId('');
      }
      return;
    }

    if (individualGraphOptions.some((option) => option.id === selectedIndividualGraphId)) {
      return;
    }

    const preferredGraphId =
      selectedGraphId && individualGraphOptions.some((option) => option.id === selectedGraphId)
        ? selectedGraphId
        : individualGraphOptions[0].id;
    setSelectedIndividualGraphId(preferredGraphId);
  }, [individualGraphOptions, pageMode, selectedGraphId, selectedIndividualGraphId]);

  const loadRowFilterOptions = useCallback(
    async (row: ViewFilterDraft, graphIds: string[]): Promise<FilterOptionsResponse> => {
      const apiUrl = getApiUrl();
      const params = new URLSearchParams({
        workspace_id: workspaceId,
      });
      const names = graphIds.length > 0 ? graphIds : ['default'];
      for (const graphId of names) {
        params.append('graph_names', graphId);
      }
      if (row.subject_uri.trim()) params.set('subject_uri', row.subject_uri.trim());
      if (row.predicate_uri.trim()) params.set('predicate_uri', row.predicate_uri.trim());
      if (row.object_uri.trim()) params.set('object_uri', row.object_uri.trim());
      const response = await authFetch(`${apiUrl}/api/view/filters/options?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Failed to load filter options: ${response.status}`);
      }
      const data = await response.json();
      return {
        subjects: Array.isArray(data?.subjects) ? data.subjects : [],
        predicates: Array.isArray(data?.predicates) ? data.predicates : [],
        objects: Array.isArray(data?.objects) ? data.objects : [],
      };
    },
    [workspaceId]
  );

  const loadViewFilterPreview = useCallback(
    async (graphIds: string[], filters: ViewFilterDraft[]) => {
      const requestId = ++viewPreviewRequestIdRef.current;
      const shouldPreview = filters.some(
        (item) =>
          item.subject_uri.trim().length > 0 ||
          (item.predicate_uri.trim().length > 0 && item.object_uri.trim().length > 0)
      );
      if (!shouldPreview) {
        if (requestId === viewPreviewRequestIdRef.current) {
          setTriplePreview({
            count: 0,
            individual_count: 0,
            object_properties_count: 0,
            data_properties_count: 0,
            rows: [],
          });
          setPreviewLoading(false);
        }
        return;
      }

      const apiUrl = getApiUrl();
      setPreviewLoading(true);
      try {
        const response = await authFetch(`${apiUrl}/api/view/filters/preview`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_names: graphIds.length > 0 ? graphIds : ['default'],
            filters,
            limit: 10,
          }),
        });
        if (!response.ok) {
          throw new Error(`Failed to preview triples: ${response.status}`);
        }
        const data = await response.json();
        if (requestId !== viewPreviewRequestIdRef.current) {
          return;
        }
        setTriplePreview({
          count: typeof data?.count === 'number' ? data.count : 0,
          individual_count:
            typeof data?.individual_count === 'number' ? data.individual_count : 0,
          object_properties_count:
            typeof data?.object_properties_count === 'number' ? data.object_properties_count : 0,
          data_properties_count:
            typeof data?.data_properties_count === 'number' ? data.data_properties_count : 0,
          rows: Array.isArray(data?.rows) ? data.rows : [],
        });
      } catch (err) {
        console.error('Failed to load triple preview:', err);
        if (requestId === viewPreviewRequestIdRef.current) {
          setTriplePreview({
            count: 0,
            individual_count: 0,
            object_properties_count: 0,
            data_properties_count: 0,
            rows: [],
          });
        }
      } finally {
        if (requestId === viewPreviewRequestIdRef.current) {
          setPreviewLoading(false);
        }
      }
    },
    [workspaceId]
  );

  useEffect(() => {
    if (pageMode !== 'create-view') return;
    const graphIds = selectedViewGraphIds.length > 0 ? selectedViewGraphIds : ['default'];
    const optionsRequestId = ++viewFilterOptionsRequestIdRef.current;

    Promise.all(viewFilters.map((row) => loadRowFilterOptions(row, graphIds)))
      .then((rows) => {
        if (optionsRequestId !== viewFilterOptionsRequestIdRef.current) {
          return;
        }
        setViewFilterOptions(rows);
      })
      .catch((err) => {
        console.error('Failed to load filter options:', err);
        if (optionsRequestId !== viewFilterOptionsRequestIdRef.current) {
          return;
        }
        setViewFilterOptions(
          viewFilters.map(() => ({ subjects: [], predicates: [], objects: [] }))
        );
      });

    void loadViewFilterPreview(graphIds, viewFilters);
  }, [loadRowFilterOptions, loadViewFilterPreview, pageMode, selectedViewGraphIds, viewFilters]);

  const resetCreateIndividualForm = () => {
    setIndividualLabel('');
    setSelectedClassId('');
    setSelectedIndividualGraphId('');
    setCreateError(null);
  };

  const closeCreateIndividualForm = () => {
    resetCreateIndividualForm();
    setPageMode('graph');
    setActiveViewType('entities');
    router.push(`/workspace/${workspaceId}/graph`);
  };

  const closeSparqlView = () => {
    setPageMode('graph');
    setActiveViewType('entities');
    router.push(`/workspace/${workspaceId}/graph`);
  };

  const closeCreateViewForm = () => {
    setPageMode('graph');
    setEditingViewId(null);
    setViewName('');
    setViewDescription('');
    setSelectedViewGraphIds([]);
    setViewFilters([{ subject_uri: '', predicate_uri: '', object_uri: '' }]);
    setViewFormError(null);
    router.push(`/workspace/${workspaceId}/graph`);
  };

  const closeCreateGraphForm = () => {
    setPageMode('graph');
    setGraphName('');
    setGraphDescription('');
    setGraphFormError(null);
    router.push(`/workspace/${workspaceId}/graph`);
  };

  const handleCreateGraph = async () => {
    const label = graphName.trim();
    if (!label) {
      setGraphFormError('Name is required.');
      return;
    }
    setGraphFormError(null);
    setCreatingGraph(true);
    try {
      const apiUrl = getApiUrl();
      const body: { workspace_id: string; label: string; description?: string } = {
        workspace_id: workspaceId,
        label,
      };
      if (graphDescription.trim()) body.description = graphDescription.trim();
      const response = await authFetch(`${apiUrl}/api/graph/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Failed to create graph: ${response.status}`);
      }
      const created = await response.json();
      const createdId = typeof created?.id === 'string' ? created.id : null;
      if (!createdId) {
        throw new Error('Created graph response is missing an id.');
      }
      setActiveSavedView(null);
      selectGraph(createdId);
      setVisibleGraphs([createdId]);
      setActiveViewType('entities');
      closeCreateGraphForm();
      clearGraphPageCaches();
      await loadFromApi({ force: true });
      window.dispatchEvent(new CustomEvent('graph-list-update'));
    } catch (err) {
      setGraphFormError(err instanceof Error ? err.message : 'Failed to create graph');
    } finally {
      setCreatingGraph(false);
    }
  };

  const handleCreateView = async () => {
    const normalizedName = viewName.trim();
    if (!normalizedName) {
      setViewFormError('Name is required.');
      return;
    }
    const graphIds = selectedViewGraphIds.length > 0 ? selectedViewGraphIds : ['default'];
    const normalizedFilters = viewFilters
      .map((item) => ({
        subject_uri: item.subject_uri.trim(),
        predicate_uri: item.predicate_uri.trim(),
        object_uri: item.object_uri.trim(),
      }))
      .filter((item) => item.subject_uri || item.predicate_uri || item.object_uri);

    if (normalizedFilters.length === 0) {
      setViewFormError('Add at least one filter with at least one of subject, predicate, or object.');
      return;
    }

    setViewFormError(null);
    const apiUrl = getApiUrl();
    const payload = {
      workspace_id: workspaceId,
      name: normalizedName,
      description: viewDescription.trim() || undefined,
      graph_names: graphIds,
      filters: normalizedFilters,
    };

    try {
      let savedViewId: string | null = null;
      if (editingViewId) {
        const response = await authFetch(
          `${apiUrl}/api/view/${encodeURIComponent(editingViewId)}?workspace_id=${encodeURIComponent(workspaceId)}`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          }
        );
        if (!response.ok) {
          setViewFormError('Failed to update view.');
          return;
        }
        const updated = await response.json();
        savedViewId = typeof updated?.id === 'string' ? updated.id : editingViewId;
      } else {
        const response = await authFetch(`${apiUrl}/api/view/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          setViewFormError('Failed to create view.');
          return;
        }
        const created = await response.json();
        savedViewId =
          typeof created?.id === 'string'
            ? created.id
            : typeof created?.view_id === 'string'
              ? created.view_id
              : typeof created?.uri === 'string'
                ? created.uri.split('/').pop() ?? null
                : typeof created?.view_uri === 'string'
                  ? created.view_uri.split('/').pop() ?? null
                  : null;
      }

      await loadViewsFromApi();
      if (savedViewId) {
        setActiveSavedView(savedViewId);
      }
      setVisibleGraphs(graphIds);
      setActiveViewType('entities');
      closeCreateViewForm();
    } catch (err) {
      console.error('Failed to save graph view:', err);
      setViewFormError('Failed to reach API. Verify backend is running and API URL is reachable.');
    }
  };

  useEffect(() => {
    if (pageMode !== 'create-view') return;

    if (editingView) {
      setViewName(editingView.name ?? '');
      setViewDescription('');
      setSelectedViewGraphIds(Array.isArray(editingView.graphIds) ? editingView.graphIds : []);
      const normalizedFilters = Array.isArray(editingView.filters)
        ? editingView.filters
          .map((item) => ({
            subject_uri: item.subject_uri ?? '',
            predicate_uri: item.predicate_uri ?? '',
            object_uri: item.object_uri ?? '',
          }))
          .filter(
            (item) =>
              (item.subject_uri && item.subject_uri.trim()) ||
              (item.predicate_uri && item.predicate_uri.trim()) ||
              (item.object_uri && item.object_uri.trim())
          )
        : [];
      setViewFilters(
        normalizedFilters.length > 0
          ? normalizedFilters
          : [{ subject_uri: '', predicate_uri: '', object_uri: '' }]
      );
      setViewFormError(null);
      return;
    }

    setViewName('');
    setViewDescription('');
    setSelectedViewGraphIds([]);
    setViewFilters([{ subject_uri: '', predicate_uri: '', object_uri: '' }]);
    setViewFilterOptions([]);
    setTriplePreview({
      count: 0,
      individual_count: 0,
      object_properties_count: 0,
      data_properties_count: 0,
      rows: [],
    });
    setViewFormError(null);
  }, [pageMode, editingView]);

  const handleCreateIndividual = async () => {
    const normalizedLabel = individualLabel.trim();
    if (!normalizedLabel) return;
    if (!selectedIndividualGraphId) {
      setCreateError('Please select a graph.');
      return;
    }

    setCreatingIndividual(true);
    setCreateError(null);
    try {
      setActiveSavedView(null);
      selectGraph(selectedIndividualGraphId);
      setVisibleGraphs([selectedIndividualGraphId]);
      const selectedClass = availableClasses.find((item) => item.id === selectedClassId);
      const apiUrl = getApiUrl();
      const response = await authFetch(`${apiUrl}/api/graph/nodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          type: 'Individual',
          label: normalizedLabel,
          properties: selectedClass
            ? {
              class_id: selectedClass.id,
              class_label: selectedClass.name,
            }
            : {},
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed with status ${response.status}`);
      }

      clearGraphPageCaches();
      await loadFromApi({ force: true });
      closeCreateIndividualForm();
    } catch (err) {
      console.error('Failed to create individual:', err);
      setCreateError('Failed to create individual. Please try again.');
    } finally {
      setCreatingIndividual(false);
    }
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  
  // Filter nodes based on search query (memoized)
  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return nodes;
    const q = searchQuery.toLowerCase();
    return nodes.filter((node) =>
      node.label.toLowerCase().includes(q) ||
      node.type.toLowerCase().includes(q) ||
      node.id.toLowerCase().includes(q)
    );
  }, [nodes, searchQuery]);
  
  // Filter edges to only include edges where both source and target are in filtered nodes (memoized)
  const filteredEdges = useMemo(() => {
    if (!searchQuery.trim()) return edges;
    const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
    return edges.filter((edge) =>
      filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)
    );
  }, [edges, filteredNodes, searchQuery]);
  
  // Calculate statistics (memoized)
  const stats = useMemo(() => ({
    totalNodes: nodes.length,
    totalEdges: edges.length,
    avgDegree: nodes.length > 0 ? (2 * edges.length) / nodes.length : 0,
    density: nodes.length > 1 ? (2 * edges.length) / (nodes.length * (nodes.length - 1)) : 0,
    connectedComponents: 1,
    nodesByType: nodes.reduce((acc, node) => {
      acc[node.type] = (acc[node.type] || 0) + 1;
      return acc;
    }, {} as Record<string, number>),
  }), [nodes, edges]);

  const handleRunQuery = useCallback(() => {
    if (!currentQuery.trim()) return;
    
    setQueryError(null);
    setQueryResults(null);
    
    try {
      // Simple query executor on in-memory data
      // Convert nodes and edges to triples for querying
      const triples: { subject: string; predicate: string; object: string; subjectLabel?: string; objectLabel?: string }[] = [];
      
      // Add node type triples
      nodes.forEach((node) => {
        triples.push({
          subject: node.id,
          predicate: 'a',
          object: node.type,
          subjectLabel: node.label,
        });
        triples.push({
          subject: node.id,
          predicate: 'rdfs:label',
          object: node.label,
          subjectLabel: node.label,
        });
      });
      
      // Add edge triples
      edges.forEach((edge) => {
        const sourceNode = nodes.find((n) => n.id === edge.source);
        const targetNode = nodes.find((n) => n.id === edge.target);
        triples.push({
          subject: edge.source,
          predicate: edge.type,
          object: edge.target,
          subjectLabel: sourceNode?.label,
          objectLabel: targetNode?.label,
        });
      });
      
      // Parse query to extract LIMIT
      const limitMatch = currentQuery.match(/LIMIT\s+(\d+)/i);
      const limit = limitMatch ? parseInt(limitMatch[1], 10) : 100;
      
      // Generate results based on query type
      let results: Record<string, string>[] = [];
      
      if (currentQuery.toLowerCase().includes('select ?subject ?predicate ?object') || 
          currentQuery.toLowerCase().includes('select ?s ?p ?o')) {
        // All triples query
        results = triples.slice(0, limit).map((t) => ({
          subject: t.subjectLabel || t.subject,
          predicate: t.predicate,
          object: t.objectLabel || t.object,
        }));
      } else if (currentQuery.toLowerCase().includes('select ?node ?type ?label')) {
        // Nodes query
        results = nodes.slice(0, limit).map((n) => ({
          node: n.id,
          type: n.type,
          label: n.label,
        }));
      } else if (currentQuery.toLowerCase().includes('select ?predicate ?object')) {
        // Node connections query - find the node ID in the query
        const nodeMatch = currentQuery.match(/<([^>]+)>\s*\?predicate/);
        const nodeId = nodeMatch ? nodeMatch[1] : 'node-nexus-platform';
        results = triples
          .filter((t) => t.subject === nodeId)
          .slice(0, limit)
          .map((t) => ({
            predicate: t.predicate,
            object: t.objectLabel || t.object,
          }));
      } else if (currentQuery.toLowerCase().includes('count')) {
        // Count by type query
        const typeCounts: Record<string, number> = {};
        nodes.forEach((n) => {
          typeCounts[n.type] = (typeCounts[n.type] || 0) + 1;
        });
        results = Object.entries(typeCounts)
          .sort((a, b) => b[1] - a[1])
          .map(([type, count]) => ({ type, count: count.toString() }));
      } else if (currentQuery.toLowerCase().includes('agent')) {
        // Agents query
        const agentEdges = edges.filter((e) => e.type === 'has agent');
        results = agentEdges.map((e) => {
          const agent = nodes.find((n) => n.id === e.target);
          const capabilities = edges
            .filter((cap) => cap.source === e.target && cap.type === 'has capability')
            .map((cap) => nodes.find((n) => n.id === cap.target)?.label || cap.target)
            .join(', ');
          return {
            agent: e.target,
            agentLabel: agent?.label || e.target,
            capabilities: capabilities || 'none',
          };
        });
      } else {
        // Default: return all triples
        results = triples.slice(0, limit).map((t) => ({
          subject: t.subjectLabel || t.subject,
          predicate: t.predicate,
          object: t.objectLabel || t.object,
        }));
      }
      
      setQueryResults(results);
    } catch (err) {
      setQueryError(err instanceof Error ? err.message : 'Query execution failed');
    }
  }, [currentQuery, nodes, edges]);

  const handleSaveQuery = useCallback(() => {
    if (currentQuery.trim()) {
      // TODO: Replace with proper dialog and save via API
      console.log('Saving query:', currentQuery);
    }
  }, [currentQuery]);

  const handleZoomChange = useCallback((level: number) => {
    setZoomLevel(Math.max(0.1, Math.min(3, level)));
  }, []);

  return (
    <div className="flex h-full flex-col">
      <Header />

      <div className="flex flex-1 overflow-hidden">
        {/* Main Content */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Toolbar */}
          <div className="flex h-10 items-center justify-between border-b bg-muted/30 px-4">
            {pageMode === 'graph' ? (
              <>
                <div className="flex items-center gap-1">
                  {GRAPH_VIEW_TYPES.map((view) => {
                    const Icon = view.icon;
                    return (
                      <button
                        key={view.id}
                        onClick={() => setActiveViewType(view.id)}
                        className={cn(
                          'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                          activeViewType === view.id
                            ? 'bg-background'
                            : 'text-muted-foreground hover:bg-background'
                        )}
                      >
                        <Icon size={14} />
                        {view.label}
                      </button>
                    );
                  })}
                </div>
                <div className="flex items-center gap-2" />
              </>
            ) : pageMode === 'sparql' ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Code size={14} />
                SPARQL Query
              </div>
            ) : pageMode === 'create-graph' ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Database size={14} />
                Create New Graph
              </div>
            ) : pageMode === 'create-view' ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Filter size={14} />
                {editingView ? 'Edit View' : 'Create New View'}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <UserPlus size={14} className="text-orange-500 dark:text-orange-400" />
                Create New Individual
              </div>
            )}
          </div>

          {/* Content based on view type */}
          <div className="flex flex-1 overflow-hidden">
            {pageMode === 'create-individual' && (
              <div className="flex flex-1 flex-col overflow-y-auto bg-card p-6">
                <div className="mx-auto w-full max-w-2xl">
                  <div className="mb-6 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <UserPlus size={24} className="text-orange-500 dark:text-orange-400" />
                      <h2 className="text-lg font-semibold">Create New Individual</h2>
                    </div>
                    <button
                      onClick={closeCreateIndividualForm}
                      className="rounded p-2 text-muted-foreground hover:bg-muted"
                      title="Close"
                    >
                      <X size={20} />
                    </button>
                  </div>

                  <div className="space-y-6">
                    <div>
                      <label className="mb-2 block text-sm font-medium">Label *</label>
                      <input
                        type="text"
                        value={individualLabel}
                        onChange={(event) => setIndividualLabel(event.target.value)}
                        placeholder="e.g., Acme Corporation, Process-001"
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium">Graph *</label>
                      <select
                        value={selectedIndividualGraphId}
                        onChange={(event) => setSelectedIndividualGraphId(event.target.value)}
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                        disabled={creatingIndividual || individualGraphOptions.length === 0}
                      >
                        <option value="">
                          {individualGraphOptions.length > 0
                            ? 'Select a graph'
                            : 'No graph available (schema and nexus are excluded)'}
                        </option>
                        {individualGraphOptions.map((graph) => (
                          <option key={graph.id} value={graph.id}>
                            {graph.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium">Class</label>
                      <ClassOptionDropdown
                        options={availableClasses}
                        value={selectedClassId}
                        onChange={setSelectedClassId}
                        placeholder={classesLoading ? 'Loading classes...' : 'Select a class'}
                        disabled={classesLoading}
                      />
                    </div>

                    {createError && (
                      <p className="text-sm text-red-500">{createError}</p>
                    )}

                    <div className="flex gap-3 pt-4">
                      <button
                        onClick={closeCreateIndividualForm}
                        className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleCreateIndividual}
                        disabled={!individualLabel.trim() || !selectedIndividualGraphId || creatingIndividual}
                        className={cn(
                          'flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                          'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'
                        )}
                      >
                        {creatingIndividual ? <Loader2 size={16} className="animate-spin" /> : <UserPlus size={16} className="text-orange-500 dark:text-orange-400" />}
                        Create Individual
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {pageMode === 'create-graph' && (
              <div className="flex flex-1 flex-col bg-card p-6">
                <div className="mx-auto w-full max-w-2xl">
                  <div className="mb-6 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Database size={24} className="text-workspace-accent" />
                      <h2 className="text-lg font-semibold">Create New Graph</h2>
                    </div>
                    <button
                      onClick={closeCreateGraphForm}
                      className="rounded p-2 text-muted-foreground hover:bg-muted"
                      title="Close"
                    >
                      <X size={20} />
                    </button>
                  </div>

                  <div className="space-y-6">
                    {graphFormError && (
                      <p className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-2 text-sm text-destructive">
                        {graphFormError}
                      </p>
                    )}
                    <div>
                      <label className="mb-2 block text-sm font-medium">Name *</label>
                      <input
                        type="text"
                        value={graphName}
                        onChange={(e) => setGraphName(e.target.value)}
                        placeholder="e.g., My ontology, Project graph"
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium">Description (optional)</label>
                      <textarea
                        value={graphDescription}
                        onChange={(e) => setGraphDescription(e.target.value)}
                        placeholder="Describe what this graph is used for"
                        rows={3}
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={closeCreateGraphForm}
                        className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleCreateGraph}
                        disabled={!graphName.trim() || creatingGraph}
                        className={cn(
                          'flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                          'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'
                        )}
                      >
                        {creatingGraph ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
                        Create Graph
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {pageMode === 'create-view' && (
              <div className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-card p-6">
                <div className="mx-auto w-full max-w-2xl">
                  <div className="mb-6 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Filter size={24} className="text-workspace-accent" />
                      <h2 className="text-lg font-semibold">{editingView ? 'Edit View' : 'Create New View'}</h2>
                    </div>
                    <button
                      onClick={closeCreateViewForm}
                      className="rounded p-2 text-muted-foreground hover:bg-muted"
                      title="Close"
                    >
                      <X size={20} />
                    </button>
                  </div>

                  <div className="space-y-6">
                    <div>
                      <label className="mb-2 block text-sm font-medium">Name *</label>
                      <input
                        type="text"
                        value={viewName}
                        onChange={(event) => setViewName(event.target.value)}
                        placeholder="e.g., Agents only"
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium">Description</label>
                      <textarea
                        value={viewDescription}
                        onChange={(event) => setViewDescription(event.target.value)}
                        placeholder="Describe what this view shows"
                        rows={3}
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium">Graphs</label>
                      <div className="space-y-1 rounded-lg border p-3">
                        {graphOptions.map((graph) => (
                          <label key={graph.id} className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={selectedViewGraphIds.includes(graph.id)}
                              onChange={(event) => {
                                if (event.target.checked) {
                                  setSelectedViewGraphIds((prev) => [...prev, graph.id]);
                                } else {
                                  setSelectedViewGraphIds((prev) => prev.filter((id) => id !== graph.id));
                                }
                              }}
                            />
                            <span>{graph.name}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center justify-between">
                        <label className="block text-sm font-medium">Filters</label>
                        <button
                          type="button"
                          onClick={() =>
                            setViewFilters((prev) => [
                              ...prev,
                              { subject_uri: '', predicate_uri: '', object_uri: '' },
                            ])
                          }
                          className="rounded border px-2 py-1 text-xs hover:bg-muted"
                        >
                          Add Filter
                        </button>
                      </div>
                      <div className="space-y-3 rounded-lg border p-3">
                        {viewFilters.map((item, index) => (
                          <div key={`filter-${index}`} className="rounded-md border p-3">
                            <div className="mb-2 flex items-center justify-between">
                              <p className="text-xs font-medium text-muted-foreground">Filter {index + 1}</p>
                              {viewFilters.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setViewFilters((prev) => prev.filter((_, rowIndex) => rowIndex !== index))
                                  }
                                  className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
                                  title="Remove filter"
                                >
                                  <Trash2 size={14} />
                                </button>
                              )}
                            </div>
                            <div className="grid gap-2 md:grid-cols-3">
                              <FilterOptionDropdown
                                options={viewFilterOptions[index]?.subjects ?? []}
                                value={item.subject_uri}
                                onChange={(v) =>
                                  setViewFilters((prev) =>
                                    prev.map((row, rowIndex) =>
                                      rowIndex === index
                                        ? { ...row, subject_uri: v, predicate_uri: '', object_uri: '' }
                                        : row
                                    )
                                  )
                                }
                                placeholder="Subject"
                              />
                              <FilterOptionDropdown
                                options={viewFilterOptions[index]?.predicates ?? []}
                                value={item.predicate_uri}
                                onChange={(v) =>
                                  setViewFilters((prev) =>
                                    prev.map((row, rowIndex) =>
                                      rowIndex === index ? { ...row, predicate_uri: v, object_uri: '' } : row
                                    )
                                  )
                                }
                                placeholder="Predicate"
                              />
                              <FilterOptionDropdown
                                options={viewFilterOptions[index]?.objects ?? []}
                                value={item.object_uri}
                                onChange={(v) =>
                                  setViewFilters((prev) =>
                                    prev.map((row, rowIndex) =>
                                      rowIndex === index ? { ...row, object_uri: v } : row
                                    )
                                  )
                                }
                                placeholder="Object"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {viewFormError && (
                      <p className="text-sm text-red-500">{viewFormError}</p>
                    )}

                    <div className="flex gap-3 pt-4">
                      <button
                        onClick={closeCreateViewForm}
                        className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleCreateView}
                        disabled={!viewName.trim()}
                        className={cn(
                          'flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                          'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'
                        )}
                      >
                        <Filter size={16} />
                        {editingView ? 'Save View' : 'Create View'}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="mt-6 w-full">
                  <div className="mb-2">
                    <p className="text-sm font-medium">Triples Preview</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {previewLoading
                        ? 'Loading...'
                        : `Individuals: ${triplePreview.individual_count} • Object properties: ${triplePreview.object_properties_count} • Data properties: ${triplePreview.data_properties_count}`}
                    </p>
                  </div>
                  <div className="rounded-lg border">
                    <table className="w-full table-fixed text-sm">
                      <thead className="bg-muted/40 text-left">
                        <tr>
                          <th className="w-1/3 px-3 py-2 text-center font-medium">Subject</th>
                          <th className="w-1/3 px-3 py-2 text-center font-medium">Predicate</th>
                          <th className="w-1/3 px-3 py-2 text-center font-medium">Object</th>
                        </tr>
                      </thead>
                      <tbody>
                        {triplePreview.rows.length === 0 ? (
                          <tr>
                            <td colSpan={3} className="px-3 py-4 text-center text-muted-foreground">
                              No triples for current filters.
                            </td>
                          </tr>
                        ) : (
                          triplePreview.rows.slice(0, 10).map((row, rowIndex) => (
                            <tr key={`preview-${rowIndex}`} className="border-t align-top">
                              <td className="px-3 py-2">{row.subject}</td>
                              <td className="px-3 py-2">{row.predicate}</td>
                              <td className="px-3 py-2">{row.object}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {pageMode === 'graph' && activeViewType === 'overview' && (
              <div className="flex-1 overflow-auto p-6">
                <div className="mb-6 flex items-start justify-between gap-4">
                  <h2 className="text-lg font-semibold">Metrics</h2>
                  <button
                    type="button"
                    onClick={() => setPageMode('create-individual')}
                    className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
                  >
                    <UserPlus size={14} className="text-orange-500 dark:text-orange-400" />
                    Create Individual
                  </button>
                </div>
                <div className="grid grid-cols-4 gap-6">
                  <StatCard title="Instances" value={overview?.kpis.total_instances ?? stats.totalNodes} icon={Circle} />
                  <StatCard title="Relationships" value={overview?.kpis.total_relationships ?? stats.totalEdges} icon={Link2} />
                  <StatCard title="Average Degree" value={(overview?.kpis.average_degree ?? stats.avgDegree).toFixed(2)} icon={Share2} />
                  <StatCard title="Density" value={((overview?.kpis.density ?? stats.density) * 100).toFixed(1) + '%'} icon={Workflow} />
                </div>

                {((overview?.instances_by_class.length ?? 0) > 0 || Object.keys(stats.nodesByType).length > 0) && (
                  <div className="mt-8">
                    <h3 className="mb-4 font-medium">Nodes by Type</h3>
                    <div className="rounded-lg border">
                      {(overview?.instances_by_class ?? Object.entries(stats.nodesByType).map(([type, count]) => ({ type, count })))
                        .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type))
                        .map(({ type, count }) => (
                        <div key={type} className="flex items-center justify-between border-b p-3 last:border-b-0">
                          <span className="flex items-center gap-2">
                            <Box size={14} className="text-blue-500" />
                            {type}
                          </span>
                          <span className="font-medium">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {pageMode === 'graph' && activeViewType === 'entities' && (
              <div className="relative flex-1 bg-zinc-50 dark:bg-zinc-900">
                {/* Search overlay - left */}
                <div className="absolute left-4 top-4 z-10 flex gap-2">
                  <div className="flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5 shadow-sm">
                    <Search size={14} className="text-muted-foreground" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search nodes..."
                      className="w-48 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery('')}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => setShowFilters(!showFilters)}
                    className={cn(
                      'flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-sm shadow-sm hover:bg-accent',
                      showFilters && 'bg-accent'
                    )}
                  >
                    <Filter size={14} />
                    Filter
                  </button>
                  {searchQuery && (
                    <span className="flex items-center rounded-lg border bg-card/80 px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
                      Showing {filteredNodes.length} of {nodes.length} nodes
                    </span>
                  )}
                </div>
                {/* Create Individual - top right inside page */}
                <div className="absolute right-4 top-4 z-10">
                  <button
                    type="button"
                    onClick={() => setPageMode('create-individual')}
                    className="flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-sm font-medium shadow-sm hover:bg-muted"
                  >
                    <UserPlus size={14} className="text-orange-500 dark:text-orange-400" />
                    Create Individual
                  </button>
                </div>

                {/* Zoom controls - using vis-network's built-in navigation buttons */}

                {/* Graph Canvas */}
                {loading ? (
                  <div className="flex h-full items-center justify-center">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 size={20} className="animate-spin" />
                      <span>Loading NEXUS Knowledge Graph...</span>
                    </div>
                  </div>
                ) : error ? (
                  <div className="flex h-full items-center justify-center">
                    <div className="text-center">
                      <div className="mb-4 flex justify-center">
                        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100 dark:bg-red-900/30">
                          <Network size={32} className="text-red-500" />
                        </div>
                      </div>
                      <h2 className="mb-2 text-lg font-semibold">Failed to Load Graph</h2>
                      <p className="mb-4 max-w-md text-muted-foreground">{error}</p>
                      <p className="mb-4 text-sm text-muted-foreground">
                        Make sure the API is running and the database is seeded.
                      </p>
                      <button
                        onClick={() => void loadFromApi()}
                        className="flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 mx-auto"
                      >
                        <RefreshCw size={16} />
                        Retry
                      </button>
                    </div>
                  </div>
                ) : nodes.length === 0 ? (
                  <div className="flex h-full items-center justify-center">
                    <div className="text-center">
                      <div className="mb-4 flex justify-center">
                        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white dark:bg-zinc-800 shadow-sm">
                          <Network size={32} className="text-muted-foreground" />
                        </div>
                      </div>
                      <h2 className="mb-2 text-lg font-semibold">No Nodes in Graph</h2>
                      <p className="mb-4 max-w-md text-muted-foreground">
                        This workspace has no graph nodes yet. Seed the database:
                      </p>
                      <code className="rounded bg-muted px-3 py-2 text-sm">
                        cd apps/api && python seed.py --reset
                      </code>
                      <div className="mt-4">
                        <button
                          onClick={() => void loadFromApi()}
                          className="flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 mx-auto"
                        >
                          <RefreshCw size={16} />
                          Refresh
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <VisNetwork
                      nodes={filteredNodes}
                      edges={filteredEdges}
                      selectedNodeId={selectedNodeId}
                      onNodeSelect={setSelectedNodeId}
                      onEdgeSelect={setSelectedEdgeId}
                    />
                    <BFOLegend />
                  </>
                )}

              </div>
            )}

            {pageMode === 'graph' && activeViewType === 'table' && (
              <div className="flex-1 overflow-auto p-4">
                <div className="mb-4 flex items-start justify-between gap-4">
                  <h2 className="text-lg font-semibold">Table</h2>
                  <button
                    type="button"
                    onClick={() => setPageMode('create-individual')}
                    className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
                  >
                    <UserPlus size={14} className="text-orange-500 dark:text-orange-400" />
                    Create Individual
                  </button>
                </div>
                <div className="rounded-lg border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-4 py-2 text-left text-sm font-medium">ID</th>
                        <th className="px-4 py-2 text-left text-sm font-medium">Label</th>
                        <th className="px-4 py-2 text-left text-sm font-medium">Type</th>
                        <th className="px-4 py-2 text-left text-sm font-medium">Properties</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nodes.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                            No nodes in this graph
                          </td>
                        </tr>
                      ) : (
                        nodes.map((node) => (
                          <tr
                            key={node.id}
                            onClick={() => setSelectedNodeId(node.id)}
                            className={cn(
                              'cursor-pointer border-b hover:bg-muted/50',
                              selectedNodeId === node.id && 'bg-workspace-accent/10'
                            )}
                          >
                            <td className="px-4 py-2 font-mono text-xs">{node.id}</td>
                            <td className="px-4 py-2 text-sm">{node.label}</td>
                            <td className="px-4 py-2">
                              <span className="rounded bg-blue-100 dark:bg-blue-900/30 px-2 py-0.5 text-xs text-blue-700 dark:text-blue-300">
                                {node.type}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-sm text-muted-foreground">
                              {Object.keys(node.properties).length} properties
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {pageMode === 'sparql' && (
              <div className="flex flex-1 flex-col p-4">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">SPARQL Query</span>
                    <button
                      onClick={handleRunQuery}
                      disabled={!currentQuery.trim()}
                      className="flex items-center gap-1 rounded bg-workspace-accent px-3 py-1 text-sm text-white disabled:opacity-50"
                    >
                      <Play size={14} />
                      Run
                    </button>
                    <button
                      onClick={handleSaveQuery}
                      disabled={!currentQuery.trim()}
                      className="flex items-center gap-1 rounded border px-3 py-1 text-sm hover:bg-muted disabled:opacity-50"
                    >
                      <Save size={14} />
                      Save
                    </button>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={closeSparqlView}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Close SPARQL"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>

                {/* Template Queries */}
                <div className="mb-3">
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Templates</p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: 'All Triples', query: `# All triples from selected graphs\nSELECT ?subject ?predicate ?object\nFROM <${visibleGraphIds[0] || workspaceId}>\n${visibleGraphIds[1] ? `FROM <${visibleGraphIds[1]}>\n` : ''}WHERE {\n  ?subject ?predicate ?object .\n}\nLIMIT 100` },
                      { label: 'All Nodes', query: `# List all nodes with their types\nSELECT ?node ?type ?label\nFROM <${visibleGraphIds[0] || workspaceId}>\n${visibleGraphIds[1] ? `FROM <${visibleGraphIds[1]}>\n` : ''}WHERE {\n  ?node a ?type .\n  ?node rdfs:label ?label .\n}\nORDER BY ?type` },
                      { label: 'Node Connections', query: `# Find all connections for a specific node\nSELECT ?predicate ?object\nFROM <${visibleGraphIds[0] || workspaceId}>\n${visibleGraphIds[1] ? `FROM <${visibleGraphIds[1]}>\n` : ''}WHERE {\n  <node-nexus-platform> ?predicate ?object .\n}` },
                      { label: 'Cross-Graph Links', query: `# Find edges connecting different graphs\nSELECT ?subject ?predicate ?object\nFROM <${workspaceId}>\n${visibleGraphIds[1] ? `FROM <${visibleGraphIds[1]}>\n` : ''}WHERE {\n  ?subject ?predicate ?object .\n  FILTER(STRSTARTS(STR(?object), "node-"))\n}` },
                      { label: 'By Type', query: `# Count nodes by BFO type\nSELECT ?type (COUNT(?node) AS ?count)\nFROM <${visibleGraphIds[0] || workspaceId}>\n${visibleGraphIds[1] ? `FROM <${visibleGraphIds[1]}>\n` : ''}WHERE {\n  ?node a ?type .\n}\nGROUP BY ?type\nORDER BY DESC(?count)` },
                      { label: 'Agents', query: `# Find all agents and their capabilities\nSELECT ?agent ?agentLabel ?capability\nFROM <${workspaceId}>\nWHERE {\n  ?platform <has agent> ?agent .\n  ?agent rdfs:label ?agentLabel .\n  OPTIONAL { ?agent <has capability> ?capability }\n}` },
                    ].map((template) => (
                      <button
                        key={template.label}
                        onClick={() => setCurrentQuery(template.query)}
                        className="rounded border px-2 py-1 text-xs hover:bg-muted transition-colors"
                      >
                        {template.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div 
                  className="flex flex-1 flex-col min-h-0"
                  onMouseMove={(e) => {
                    if (isResizing) {
                      const container = e.currentTarget;
                      const rect = container.getBoundingClientRect();
                      const newHeight = e.clientY - rect.top - 8; // 8px offset for the resizer
                      setEditorHeight(Math.max(100, Math.min(newHeight, rect.height - 100)));
                    }
                  }}
                  onMouseUp={() => setIsResizing(false)}
                  onMouseLeave={() => setIsResizing(false)}
                >
                  <textarea
                    value={currentQuery}
                    onChange={(e) => setCurrentQuery(e.target.value)}
                    placeholder={`SELECT ?s ?p ?o
WHERE {
  ?s ?p ?o .
}
LIMIT 100`}
                    style={{ height: editorHeight }}
                    className="shrink-0 resize-none rounded-lg border bg-zinc-900 p-4 font-mono text-sm text-green-400 outline-none"
                  />
                  
                  {/* Draggable Resizer */}
                  <div
                    className="h-2 cursor-row-resize flex items-center justify-center group"
                    onMouseDown={() => setIsResizing(true)}
                  >
                    <div className="w-12 h-1 rounded-full bg-border group-hover:bg-muted-foreground transition-colors" />
                  </div>
                  
                  {/* Query Results */}
                  <div className="flex-1 min-h-0 overflow-hidden rounded-lg border">
                    {queryError && (
                      <div className="p-4 text-sm text-red-500 bg-red-50 dark:bg-red-900/20">
                        Error: {queryError}
                      </div>
                    )}
                    {queryResults && queryResults.length === 0 && (
                      <div className="p-4 text-sm text-muted-foreground">
                        No results found.
                      </div>
                    )}
                    {queryResults && queryResults.length > 0 && (
                      <div className="h-full overflow-auto">
                        <table className="w-full text-sm">
                          <thead className="sticky top-0 bg-muted">
                            <tr>
                              {Object.keys(queryResults[0]).map((col) => (
                                <th key={col} className="px-3 py-2 text-left font-medium text-muted-foreground border-b">
                                  ?{col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {queryResults.map((row, i) => (
                              <tr key={i} className="border-b border-border/50 hover:bg-muted/30">
                                {Object.values(row).map((val, j) => (
                                  <td key={j} className="px-3 py-1.5 truncate max-w-[200px]" title={val}>
                                    {val}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <div className="px-3 py-2 text-xs text-muted-foreground border-t bg-muted/30">
                          {queryResults.length} result{queryResults.length !== 1 ? 's' : ''}
                        </div>
                      </div>
                    )}
                    {!queryResults && !queryError && (
                      <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
                        Click &quot;Run&quot; to execute the query
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>

        {/* Right Panel - Node Inspector */}
        {pageMode === 'graph' && selectedNode && (
          <div className="w-72 border-l bg-card">
            <div className="flex h-10 items-center justify-between border-b px-4">
              <span className="text-sm font-medium">Inspector</span>
              <button
                onClick={() => setSelectedNodeId(null)}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                title="Close inspector"
              >
                <X size={14} />
              </button>
            </div>
            
            <div className="p-4">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500 text-white">
                  <Circle size={20} />
                </div>
                <div>
                  <h3 className="font-medium">{selectedNode.label}</h3>
                  <p className="text-xs text-muted-foreground">{selectedNode.type}</p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">
                    ID
                  </label>
                  <p className="font-mono text-xs break-all">{selectedNode.id}</p>
                </div>

                <div>
                  <label className="mb-2 block text-xs font-medium text-muted-foreground">
                    Properties
                  </label>
                  {Object.keys(selectedNode.properties).length === 0 ? (
                    <p className="text-sm text-muted-foreground">No properties</p>
                  ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {Object.entries(selectedNode.properties).map(([key, value]) => (
                        <div key={key} className="text-sm">
                          <span className="text-muted-foreground">{key}:</span>{' '}
                          <span className="break-all">
                            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <label className="mb-2 block text-xs font-medium text-muted-foreground">
                    Connections ({edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id).length})
                  </label>
                  {(() => {
                    const outgoing = edges.filter((e) => e.source === selectedNode.id);
                    const incoming = edges.filter((e) => e.target === selectedNode.id);
                    
                    if (outgoing.length === 0 && incoming.length === 0) {
                      return <p className="text-sm text-muted-foreground">No connections</p>;
                    }
                    
                    return (
                      <div className="space-y-3 max-h-56 overflow-y-auto">
                        {outgoing.length > 0 && (
                          <div>
                            <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Outgoing</p>
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-left text-muted-foreground">
                                  <th className="pb-1 font-medium">Predicate</th>
                                  <th className="pb-1 font-medium">Object</th>
                                </tr>
                              </thead>
                              <tbody>
                                {outgoing.map((edge) => {
                                  const targetNode = nodes.find((n) => n.id === edge.target);
                                  const targetLabelFromProperties = typeof edge.properties?.target_label === 'string'
                                    ? edge.properties.target_label
                                    : undefined;
                                  return (
                                    <tr
                                      key={edge.id}
                                      className="cursor-pointer hover:bg-muted/50"
                                      onClick={() => setSelectedNodeId(edge.target)}
                                    >
                                      <td className="py-0.5 pr-2 text-workspace-accent">{edge.type}</td>
                                      <td className="py-0.5 truncate max-w-[120px]">
                                        {targetNode?.label || edge.targetLabel || targetLabelFromProperties || edge.target}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}
                        {incoming.length > 0 && (
                          <div>
                            <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Incoming</p>
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-left text-muted-foreground">
                                  <th className="pb-1 font-medium">Subject</th>
                                  <th className="pb-1 font-medium">Predicate</th>
                                </tr>
                              </thead>
                              <tbody>
                                {incoming.map((edge) => {
                                  const sourceNode = nodes.find((n) => n.id === edge.source);
                                  return (
                                    <tr
                                      key={edge.id}
                                      className="cursor-pointer hover:bg-muted/50"
                                      onClick={() => setSelectedNodeId(edge.source)}
                                    >
                                      <td className="py-0.5 pr-2 truncate max-w-[120px]">{sourceNode?.label || edge.source}</td>
                                      <td className="py-0.5 text-workspace-accent">{edge.type}</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              </div>

              <div className="mt-6 flex gap-2">
                <button 
                  onClick={async () => {
                    // TODO: Add proper edit dialog
                    const newLabel = prompt('New label:', selectedNode.label);
                    if (newLabel && newLabel !== selectedNode.label) {
                      try {
                        const { authFetch } = await import('@/stores/auth');
                        await authFetch(`/api/graph/nodes/${selectedNode.id}`, {
                          method: 'PUT',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            label: newLabel,
                            type: selectedNode.type,
                            properties: selectedNode.properties,
                          }),
                        });
                        // Refresh graph data
                        window.location.reload();
                      } catch (error) {
                        console.error('Failed to update node:', error);
                        alert('Failed to update node');
                      }
                    }
                  }}
                  className="flex-1 rounded border px-3 py-1.5 text-sm hover:bg-muted"
                >
                  Edit
                </button>
                <button 
                  onClick={async () => {
                    if (confirm(`Delete node "${selectedNode.label}"?`)) {
                      try {
                        const { authFetch } = await import('@/stores/auth');
                        await authFetch(`/api/graph/nodes/${selectedNode.id}`, {
                          method: 'DELETE',
                        });
                        setSelectedNodeId(null);
                        // Refresh graph data
                        window.location.reload();
                      } catch (error) {
                        console.error('Failed to delete node:', error);
                        alert('Failed to delete node');
                      }
                    }
                  }}
                  className="rounded border px-3 py-1.5 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-2 flex items-center gap-2 text-muted-foreground">
        <Icon size={16} />
        <span className="text-sm">{title}</span>
      </div>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}
