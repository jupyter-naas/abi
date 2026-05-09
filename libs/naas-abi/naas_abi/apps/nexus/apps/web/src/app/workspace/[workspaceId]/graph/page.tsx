'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { useQueryClient } from '@tanstack/react-query';
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
  GitBranch,
  ArrowRight,
  Users,
  Hash,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useKnowledgeGraphStore,
  type GraphViewType,
  type GraphTripleFilter,
  type GraphView,
} from '@/stores/knowledge-graph';
import {
  useGraphList,
  useGraphNetwork,
  useGraphOverview,
  useGraphViews,
  useOntologyClasses,
  useFilterOptions,
  useTriplePreview,
  useCreateGraph,
  useCreateIndividual,
  useCreateView,
  useUpdateView,
  useUpdateNode,
  useDeleteNode,
} from './_hooks/use-graph-queries';
import { fetchNetworkParents, type GraphSelection } from '@/lib/api/graph';
import { usePrompt, useConfirm } from '@/components/ui/dialogs';
import { FilterOptionDropdown } from './_components/FilterOptionDropdown';
import { ClassOptionDropdown } from './_components/ClassOptionDropdown';
import { StatCard } from './_components/StatCard';
import { IndividualsSplitView } from './_components/IndividualsSplitView';
import type {
  FilterOption,
  GraphEdge,
  GraphNode,
  GraphOption,
  GraphPageMode,
  OntologyClassOption,
  ViewFilterDraft,
} from './_components/types';

// Dynamically import vis-network to avoid SSR issues
const VisNetwork = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.VisNetwork),
  { ssr: false, loading: () => <div className="flex h-full items-center justify-center"><span className="text-muted-foreground">Loading graph...</span></div> }
);

const BFOBucketFilters = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.BFOBucketFilters),
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

// BFO bucket resolution helpers (mirrors ontology page logic)
const BFO_BUCKET_KEYS_GRAPH = new Set([
  'Material Entity', 'Process', 'Temporal Region', 'Site', 'Quality', 'Realizable', 'GDC',
]);
const ALL_BFO_BUCKETS_GRAPH = new Set([...BFO_BUCKET_KEYS_GRAPH, 'Unknown']);

const BFO_URI_TO_BUCKET_GRAPH: Record<string, string> = {
  'http://purl.obolibrary.org/obo/BFO_0000040': 'Material Entity',
  'http://purl.obolibrary.org/obo/BFO_0000015': 'Process',
  'http://purl.obolibrary.org/obo/BFO_0000008': 'Temporal Region',
  'http://purl.obolibrary.org/obo/BFO_0000029': 'Site',
  'http://purl.obolibrary.org/obo/BFO_0000031': 'GDC',
  'http://purl.obolibrary.org/obo/BFO_0000019': 'Quality',
  'http://purl.obolibrary.org/obo/BFO_0000017': 'Realizable',
};

function resolveGraphNodeBucket(node: GraphNode): string {
  if (BFO_BUCKET_KEYS_GRAPH.has(node.type)) return node.type;
  const bfoParentIri = node.properties?.bfo_parent_iri as string | undefined;
  if (bfoParentIri && bfoParentIri in BFO_URI_TO_BUCKET_GRAPH) return BFO_URI_TO_BUCKET_GRAPH[bfoParentIri];
  const parentIri = node.properties?.parent_iri as string | undefined;
  if (parentIri && parentIri in BFO_URI_TO_BUCKET_GRAPH) return BFO_URI_TO_BUCKET_GRAPH[parentIri];
  return 'Unknown';
}

const GRAPH_VIEW_TYPES: { id: GraphViewType; label: string; icon: React.ElementType }[] = [
  { id: 'entities', label: 'Network', icon: Network },
  { id: 'overview', label: 'Metrics', icon: Eye },
  { id: 'individuals', label: 'Individuals', icon: Users },
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


// Cache invalidation: the workspace `QueryProvider` listens for the
// `graph-cache-refresh` window event and invalidates ['graph'] / ['ontology']
// keys, so external callers (agent tools, bulk imports) keep working without
// coupling to this module.

export default function GraphPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const workspaceId = params.workspaceId as string;

  // UI state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  // BFO bucket filters — empty = no filter (show all)
  const [activeBuckets, setActiveBuckets] = useState<Set<string>>(new Set());
  const handleBucketToggle = useCallback((bucketType: string) => {
    setActiveBuckets((prev) => {
      const next = new Set(prev);
      if (next.has(bucketType)) { next.delete(bucketType); } else { next.add(bucketType); }
      return next;
    });
    setStabilizeKey((k) => k + 1);
  }, []);

  // Per-node visibility overrides — nodes in this set are hidden from the graph
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());
  const handleNodeToggle = useCallback((nodeId: string) => {
    setHiddenNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) { next.delete(nodeId); } else { next.add(nodeId); }
      return next;
    });
  }, []);

  // Node display limit — how many nodes to render in the graph canvas
  const [nodeDisplayLimit, setNodeDisplayLimit] = useState(200);

  // Parents hierarchy filter (like SubclassOf in ontology page)
  const [parentsLevels, setParentsLevels] = useState(0);
  const [loadingNextParentLevel, setLoadingNextParentLevel] = useState(false);
  const [hierarchyByLevel, setHierarchyByLevel] = useState<Array<{
    nodes: GraphNode[];
    edges: GraphEdge[];
  }>>([]);

  const [showRelations, setShowRelations] = useState(true);

  // Increment to trigger physics re-layout in VisNetwork
  const [stabilizeKey, setStabilizeKey] = useState(0);
  const {
    activeViewType,
    setActiveViewType,
    selectedGraphId,
    visibleGraphIds,
    selectGraph,
    setVisibleGraphs,
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
  const [createError, setCreateError] = useState<string | null>(null);
  const [selectedIndividualGraphId, setSelectedIndividualGraphId] = useState('');
  const [viewName, setViewName] = useState('');
  const [selectedViewGraphIds, setSelectedViewGraphIds] = useState<string[]>([]);
  const [viewFilters, setViewFilters] = useState<ViewFilterDraft[]>([
    { subject_uri: '', predicate_uri: '', object_uri: '' },
  ]);
  const [viewFormError, setViewFormError] = useState<string | null>(null);
  const [viewDescription, setViewDescription] = useState('');
  const [editingViewId, setEditingViewId] = useState<string | null>(null);
  const [graphName, setGraphName] = useState('');
  const [graphDescription, setGraphDescription] = useState('');
  const [graphFormError, setGraphFormError] = useState<string | null>(null);

  // Server data via TanStack Query.
  const graphListQuery = useGraphList(workspaceId);
  const graphOptions = useMemo<GraphOption[]>(
    () => graphListQuery.data?.items ?? [],
    [graphListQuery.data],
  );
  const knownGraphIds = useMemo(() => graphOptions.map((g) => g.id), [graphOptions]);

  const viewsQuery = useGraphViews(workspaceId);
  const apiViews: GraphView[] = useMemo(
    () =>
      (viewsQuery.data ?? []).map((v) => ({
        id: v.id,
        name: v.label || v.id,
        scope: v.scope,
        userId: v.user_id ?? undefined,
        type: 'entities' as const,
        graphIds: v.graph_names ?? [],
        filters: (v.graph_filters ?? []).map(
          (uri) =>
            ({
              subject_uri: '',
              predicate_uri: '',
              object_uri: '',
              uri,
            }) as GraphTripleFilter,
        ),
        createdAt: v.created_at ? new Date(v.created_at) : new Date(),
      })),
    [viewsQuery.data],
  );

  // Sync view list into Zustand for components elsewhere that subscribe to it.
  useEffect(() => {
    setViews(apiViews);
  }, [apiViews, setViews]);

  const activeSavedView = useMemo(
    () => apiViews.find((view) => view.id === activeSavedViewId) ?? null,
    [apiViews, activeSavedViewId],
  );
  const editingView = useMemo(
    () => (editingViewId ? apiViews.find((view) => view.id === editingViewId) ?? null : null),
    [apiViews, editingViewId],
  );

  const graphSelection: GraphSelection = useMemo(
    () => ({
      workspaceId,
      graphId: selectedGraphId,
      visibleGraphIds,
      savedViewId: activeSavedView?.id ?? null,
      knownGraphIds,
    }),
    [workspaceId, selectedGraphId, visibleGraphIds, activeSavedView?.id, knownGraphIds],
  );

  const networkQuery = useGraphNetwork(graphSelection, {
    enabled: graphListQuery.isFetched,
  });
  const overviewQuery = useGraphOverview(graphSelection, {
    enabled: pageMode === 'graph' && activeViewType === 'overview',
  });

  const nodes = useMemo<GraphNode[]>(
    () =>
      (networkQuery.data?.nodes ?? []).map((n) => ({
        id: n.id,
        label: n.label,
        type: n.type,
        properties: n.properties ?? {},
        x: n.properties?.x as number | undefined,
        y: n.properties?.y as number | undefined,
      })),
    [networkQuery.data],
  );
  const edges = useMemo<GraphEdge[]>(
    () =>
      (networkQuery.data?.edges ?? []).map((e) => ({
        id: e.id,
        source: e.source_id,
        target: e.target_id,
        sourceLabel: e.source_label,
        targetLabel: e.target_label,
        type: e.type,
        label: e.type,
        properties: e.properties ?? {},
      })),
    [networkQuery.data],
  );
  const loading = networkQuery.isPending;
  const error = networkQuery.error
    ? networkQuery.error instanceof Error
      ? networkQuery.error.message
      : 'Failed to load graph'
    : null;
  const overview = overviewQuery.data ?? null;

  const reloadGraph = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['graph', workspaceId] });
  }, [queryClient, workspaceId]);

  const classesQuery = useOntologyClasses(pageMode === 'create-individual');
  const availableClasses = classesQuery.data ?? [];
  const classesLoading = classesQuery.isFetching;

  const individualGraphOptions = useMemo(
    () => graphOptions.filter((option) => !isSystemGraph(option)),
    [graphOptions],
  );

  // View-builder live preview + filter options.
  const viewBuilderGraphIds = useMemo(
    () => (selectedViewGraphIds.length > 0 ? selectedViewGraphIds : ['default']),
    [selectedViewGraphIds],
  );
  const filterOptionsQuery = useFilterOptions({
    workspaceId,
    graphIds: viewBuilderGraphIds,
    rows: viewFilters,
    enabled: pageMode === 'create-view',
  });
  const viewFilterOptions = filterOptionsQuery.data ?? [];
  const triplePreviewQuery = useTriplePreview({
    workspaceId,
    graphIds: viewBuilderGraphIds,
    filters: viewFilters,
    enabled: pageMode === 'create-view',
  });
  const triplePreview = useMemo(() => {
    const data = triplePreviewQuery.data;
    return {
      count: data?.count ?? 0,
      individual_count: data?.individual_count ?? 0,
      object_properties_count: data?.object_properties_count ?? 0,
      data_properties_count: data?.data_properties_count ?? 0,
      rows: data?.rows ?? [],
    };
  }, [triplePreviewQuery.data]);
  const previewLoading = triplePreviewQuery.isFetching;

  const createGraphMutation = useCreateGraph();
  const createIndividualMutation = useCreateIndividual();
  const createViewMutation = useCreateView(workspaceId);
  const updateViewMutation = useUpdateView(workspaceId);
  const updateNodeMutation = useUpdateNode(workspaceId);
  const deleteNodeMutation = useDeleteNode(workspaceId);
  const creatingIndividual = createIndividualMutation.isPending;
  const creatingGraph = createGraphMutation.isPending;

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId],
  );

  const { prompt: showPrompt, dialog: promptDialog } = usePrompt();
  const { confirm: showConfirm, dialog: confirmDialog } = useConfirm();
  const [inspectorError, setInspectorError] = useState<string | null>(null);

  const handleEditNode = useCallback(async () => {
    if (!selectedNode) return;
    const newLabel = await showPrompt({
      title: 'Edit node label',
      defaultValue: selectedNode.label,
      placeholder: 'Label',
      confirmLabel: 'Save',
    });
    if (!newLabel || newLabel === selectedNode.label) return;
    try {
      await updateNodeMutation.mutateAsync({
        id: selectedNode.id,
        label: newLabel,
        type: selectedNode.type,
        properties: selectedNode.properties,
      });
      setInspectorError(null);
    } catch (err) {
      console.error('Failed to update node:', err);
      setInspectorError('Failed to update node.');
    }
  }, [selectedNode, showPrompt, updateNodeMutation]);

  const handleDeleteNode = useCallback(async () => {
    if (!selectedNode) return;
    const ok = await showConfirm({
      title: 'Delete node',
      description: `Delete "${selectedNode.label}"? This cannot be undone.`,
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (!ok) return;
    try {
      await deleteNodeMutation.mutateAsync(selectedNode.id);
      setSelectedNodeId(null);
      setInspectorError(null);
    } catch (err) {
      console.error('Failed to delete node:', err);
      setInspectorError('Failed to delete node.');
    }
  }, [selectedNode, showConfirm, deleteNodeMutation]);

  // Reset selection and filters when the active graph identity changes.
  useEffect(() => {
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setParentsLevels(0);
    setShowRelations(true);
    setHiddenNodeIds(new Set());
    setNodeDisplayLimit(200);
  }, [selectedGraphId, activeSavedViewId]);

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
    try {
      const { id: createdId } = await createGraphMutation.mutateAsync({
        workspaceId,
        label,
        description: graphDescription.trim() || undefined,
      });
      setActiveSavedView(null);
      selectGraph(createdId);
      setVisibleGraphs([createdId]);
      setActiveViewType('entities');
      closeCreateGraphForm();
      window.dispatchEvent(new CustomEvent('graph-list-update'));
    } catch (err) {
      setGraphFormError(err instanceof Error ? err.message : 'Failed to create graph');
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
    const payload = {
      workspaceId,
      name: normalizedName,
      description: viewDescription.trim() || undefined,
      graphIds,
      filters: normalizedFilters,
    };

    try {
      const { id: savedViewId } = editingViewId
        ? await updateViewMutation.mutateAsync({ viewId: editingViewId, payload })
        : await createViewMutation.mutateAsync(payload);

      if (savedViewId) setActiveSavedView(savedViewId);
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
    // viewFilterOptions / triplePreview are derived from queries; they reset
    // automatically when `viewFilters` / `selectedViewGraphIds` change.
    setViewFormError(null);
  }, [pageMode, editingView]);

  const handleCreateIndividual = async () => {
    const normalizedLabel = individualLabel.trim();
    if (!normalizedLabel) return;
    if (!selectedIndividualGraphId) {
      setCreateError('Please select a graph.');
      return;
    }

    setCreateError(null);
    try {
      setActiveSavedView(null);
      selectGraph(selectedIndividualGraphId);
      setVisibleGraphs([selectedIndividualGraphId]);
      const selectedClass = availableClasses.find((item) => item.id === selectedClassId);
      await createIndividualMutation.mutateAsync({
        workspaceId,
        label: normalizedLabel,
        classId: selectedClass?.id,
        className: selectedClass?.name,
      });
      closeCreateIndividualForm();
    } catch (err) {
      console.error('Failed to create individual:', err);
      setCreateError('Failed to create individual. Please try again.');
    }
  };

  const handleExpandParents = useCallback(async () => {
    const nextLevel = parentsLevels + 1;
    if (hierarchyByLevel[nextLevel - 1]) {
      setParentsLevels(nextLevel);
      return;
    }
    if (loadingNextParentLevel) return;
    setLoadingNextParentLevel(true);
    try {
      const frontier: GraphNode[] =
        parentsLevels === 0
          ? nodes
          : (hierarchyByLevel[parentsLevels - 1]?.nodes ?? []);
      if (frontier.length === 0) { setParentsLevels(nextLevel); return; }

      const graphIdsForParents = selectedGraphId
        ? [selectedGraphId]
        : visibleGraphIds.filter((id) => !id.includes('#layer='));

      const data = await fetchNetworkParents(workspaceId, {
        graphIds: graphIdsForParents,
        nodeIris: frontier.map((n) => n.id),
      });

      const newNodes: GraphNode[] = data.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        type: n.type,
        properties: n.properties ?? {},
      }));
      const newEdges: GraphEdge[] = data.edges.map((e) => ({
        id: e.id,
        source: e.source_id,
        target: e.target_id,
        sourceLabel: e.source_label,
        targetLabel: e.target_label,
        type: e.type,
        label: 'is a',
        properties: { ...(e.properties ?? {}), relation_kind: 'is_a' },
      }));

      setHierarchyByLevel((prev) => {
        const updated = [...prev];
        updated[nextLevel - 1] = { nodes: newNodes, edges: newEdges };
        return updated;
      });
      setParentsLevels(nextLevel);
    } catch (err) {
      console.error('Failed to fetch parent nodes:', err);
    } finally {
      setLoadingNextParentLevel(false);
    }
  }, [parentsLevels, hierarchyByLevel, loadingNextParentLevel, nodes, selectedGraphId, visibleGraphIds, workspaceId]);

  const canExpandParentsMore =
    parentsLevels < hierarchyByLevel.length ||
    (hierarchyByLevel[parentsLevels - 1]?.nodes.length ?? 1) > 0;

  // Combined visible nodes: base + all loaded parent levels up to parentsLevels
  const allVisibleNodes = useMemo(() => {
    if (parentsLevels === 0) return nodes;
    const result = [...nodes];
    const seen = new Set(result.map((n) => n.id));
    for (let i = 0; i < parentsLevels && i < hierarchyByLevel.length; i++) {
      for (const node of hierarchyByLevel[i].nodes) {
        if (!seen.has(node.id)) { result.push(node); seen.add(node.id); }
      }
    }
    return result;
  }, [nodes, hierarchyByLevel, parentsLevels]);

  // Nodes grouped by bucket for the BFO panel checkboxes
  const nodesPerBucketForPanel = useMemo(() => {
    const map = new Map<string, Array<{ id: string; label: string }>>();
    for (const node of allVisibleNodes) {
      const bucket = resolveGraphNodeBucket(node);
      const existing = map.get(bucket) ?? [];
      existing.push({ id: node.id, label: node.label });
      map.set(bucket, existing);
    }
    for (const [, bucketNodes] of map) {
      bucketNodes.sort((a, b) => a.label.localeCompare(b.label));
    }
    return map;
  }, [allVisibleNodes]);

  // Filter nodes: search + bucket + hidden
  const filteredNodes = useMemo(() => {
    let result = allVisibleNodes;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((node) =>
        node.label.toLowerCase().includes(q) ||
        node.type.toLowerCase().includes(q) ||
        node.id.toLowerCase().includes(q)
      );
    }
    if (activeBuckets.size > 0) {
      result = result.filter((node) => activeBuckets.has(resolveGraphNodeBucket(node)));
    }
    if (hiddenNodeIds.size > 0) {
      result = result.filter((node) => !hiddenNodeIds.has(node.id));
    }
    return result;
  }, [allVisibleNodes, searchQuery, activeBuckets, hiddenNodeIds]);

  // Filter edges: relations toggle + parents levels + constrain to visible nodes
  const filteredEdges = useMemo(() => {
    const visibleNodeIds = new Set(filteredNodes.map((n) => n.id));
    let result: GraphEdge[] = [];

    // Regular relation edges
    if (showRelations) {
      result = edges.filter((e) =>
        visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
      );
    }

    // is_a edges from loaded parent levels
    for (let i = 0; i < parentsLevels && i < hierarchyByLevel.length; i++) {
      for (const edge of hierarchyByLevel[i].edges) {
        if (visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)) {
          result.push(edge);
        }
      }
    }

    return result;
  }, [edges, filteredNodes, showRelations, parentsLevels, hierarchyByLevel]);

  // Apply display limit — slice filteredNodes and constrain edges to those nodes
  const displayedNodes = useMemo(
    () => filteredNodes.slice(0, nodeDisplayLimit),
    [filteredNodes, nodeDisplayLimit]
  );

  const displayedEdges = useMemo(() => {
    const visibleIds = new Set(displayedNodes.map((n) => n.id));
    return filteredEdges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));
  }, [filteredEdges, displayedNodes]);

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
                  <StatCard title="Instances" value={overview?.kpis?.total_instances ?? stats.totalNodes} icon={Circle} />
                  <StatCard title="Relationships" value={overview?.kpis?.total_relationships ?? stats.totalEdges} icon={Link2} />
                  <StatCard title="Average Degree" value={(overview?.kpis?.average_degree ?? stats.avgDegree).toFixed(2)} icon={Share2} />
                  <StatCard title="Density" value={((overview?.kpis?.density ?? stats.density) * 100).toFixed(1) + '%'} icon={Workflow} />
                </div>

                {((overview?.instances_by_class?.length ?? 0) > 0 || Object.keys(stats.nodesByType).length > 0) && (
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

            {pageMode === 'graph' && activeViewType === 'individuals' && (
              <IndividualsSplitView
                nodes={nodes}
                edges={edges}
                loading={loading}
                error={error}
                onCreateIndividual={() => setPageMode('create-individual')}
              />
            )}

            {pageMode === 'graph' && activeViewType === 'entities' && (
              <div className="relative flex-1 bg-zinc-50 dark:bg-zinc-900">
                {/* Search + relation filters — left */}
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
                  {/* Relations toggle */}
                  <button
                    onClick={() => { setShowRelations((v) => !v); setStabilizeKey((k) => k + 1); }}
                    title="Toggle relation edges (URIRef objects, excl. rdf:type)"
                    className={cn(
                      'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs shadow-sm',
                      showRelations
                        ? 'border-foreground bg-foreground text-background'
                        : 'border-border bg-card text-muted-foreground hover:text-foreground'
                    )}
                  >
                    <ArrowRight size={12} />
                    Relations
                  </button>
                  {/* Parents filter — like SubclassOf in ontology page */}
                  <div className="flex items-center rounded-lg border bg-card shadow-sm overflow-hidden">
                    <button
                      onClick={() => parentsLevels === 0 ? handleExpandParents() : setParentsLevels(0)}
                      title={parentsLevels === 0 ? 'Show parent classes (rdf:type → rdfs:subClassOf)' : 'Hide parent hierarchy'}
                      disabled={loadingNextParentLevel}
                      className={cn(
                        'flex items-center gap-1.5 px-3 py-1.5 text-xs',
                        parentsLevels > 0 ? 'bg-foreground text-background' : 'text-muted-foreground hover:text-foreground',
                        loadingNextParentLevel && 'opacity-60 cursor-not-allowed'
                      )}
                    >
                      {loadingNextParentLevel ? <Loader2 size={12} className="animate-spin" /> : <GitBranch size={12} />}
                      Parents{parentsLevels > 0 && ` (${parentsLevels})`}
                    </button>
                    {parentsLevels > 0 && (
                      <button
                        onClick={() => setParentsLevels((v) => Math.max(0, v - 1))}
                        title="Show fewer parent levels"
                        disabled={loadingNextParentLevel}
                        className="border-l px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60"
                      >−</button>
                    )}
                    {canExpandParentsMore && (
                      <button
                        onClick={handleExpandParents}
                        title="Show more parent levels"
                        disabled={loadingNextParentLevel}
                        className="border-l px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60"
                      >+</button>
                    )}
                  </div>
                  {(searchQuery || filteredNodes.length < allVisibleNodes.length || nodeDisplayLimit < filteredNodes.length) && (
                    <span className="flex items-center rounded-lg border bg-card/80 px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
                      Showing {Math.min(nodeDisplayLimit, filteredNodes.length)} of {allVisibleNodes.length} nodes
                    </span>
                  )}
                </div>
                <BFOBucketFilters
                  activeBuckets={activeBuckets}
                  onToggle={handleBucketToggle}
                  nodesPerBucket={nodesPerBucketForPanel}
                  hiddenNodeIds={hiddenNodeIds}
                  onNodeToggle={handleNodeToggle}
                />

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
                        onClick={reloadGraph}
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
                          onClick={reloadGraph}
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
                      key={activeSavedViewId ?? selectedGraphId ?? visibleGraphIds.join(',') ?? 'default'}
                      nodes={displayedNodes}
                      edges={displayedEdges}
                      selectedNodeId={selectedNodeId}
                      onNodeSelect={setSelectedNodeId}
                      onEdgeSelect={setSelectedEdgeId}
                      stabilizeKey={stabilizeKey}
                    />
                    {filteredNodes.length > 0 && (
                      <div className="absolute bottom-4 left-4 z-10 flex flex-col gap-1.5 rounded-lg border bg-card/95 px-3 py-2 shadow-lg backdrop-blur-sm w-52">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>Nodes displayed</span>
                          <span className="font-medium tabular-nums">
                            {Math.min(nodeDisplayLimit, filteredNodes.length)}&nbsp;/&nbsp;{filteredNodes.length}
                          </span>
                        </div>
                        <input
                          type="range"
                          min={1}
                          max={filteredNodes.length}
                          value={Math.min(nodeDisplayLimit, filteredNodes.length)}
                          onChange={(e) => setNodeDisplayLimit(Number(e.target.value))}
                          className="h-1.5 w-full cursor-pointer accent-foreground"
                        />
                      </div>
                    )}
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

              {inspectorError && (
                <p className="mt-3 rounded border border-destructive/50 bg-destructive/10 px-3 py-1.5 text-xs text-destructive">
                  {inspectorError}
                </p>
              )}

              <div className="mt-6 flex gap-2">
                <button
                  type="button"
                  onClick={() => void handleEditNode()}
                  disabled={updateNodeMutation.isPending}
                  className="flex-1 rounded border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
                >
                  {updateNodeMutation.isPending ? 'Saving…' : 'Edit'}
                </button>
                <button
                  type="button"
                  onClick={() => void handleDeleteNode()}
                  disabled={deleteNodeMutation.isPending}
                  className="rounded border px-3 py-1.5 text-sm text-red-500 hover:bg-red-50 disabled:opacity-50 dark:hover:bg-red-900/20"
                >
                  {deleteNodeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
      {promptDialog}
      {confirmDialog}
    </div>
  );
}
