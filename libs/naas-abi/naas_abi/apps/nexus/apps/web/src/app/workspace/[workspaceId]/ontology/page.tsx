'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useRouter, useSearchParams, useParams } from 'next/navigation';
import { ontologySpacing } from '@/lib/ontology-spacing';
import dynamic from 'next/dynamic';
import { OntologyDictionaryEntry } from '@/components/shell/sidebar/ontology-dictionary-entry';
import { OntologySystemView } from '@/components/ontology/ontology-system-view';
import { OntologyTermNetwork } from '@/components/ontology/ontology-term-network';
import { OntologyMenuBar } from '@/components/ontology/ontology-menu-bar';
import { OntologyDashboard } from '@/components/ontology/ontology-dashboard';
import '@/components/ontology/ontology-detail.css';
import { Header } from '@/components/shell/header';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { ontologyApiParams, ontologyApiQuery } from '@/lib/ontology-query';
import {
  Network,
  X,
  Box,
  Link2,
  Loader2,
  Search,
  Type,
  GitBranch,
  AlertCircle,
  ArrowRight,
  Focus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOntologyStore } from '@/stores/ontology';
import { useOntologyIconsStore } from '@/stores/ontology-icons';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useWorkspaceStore } from '@/stores/workspace';
import { termTabs, termViews, kindForView, termRoute, viewRoute, ontologyBrowser, normalizeOntologyRoute, lastOntologyRoute, rememberOntologyRoute } from '@/lib/ontology-navigation';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { buildHoverTitle } from '@/components/graph/vis-network';

type OntologyOverviewGraphNode = {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
};

type OntologyOverviewGraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  label?: string;
  properties?: Record<string, unknown>;
};

const VisNetwork = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.VisNetwork),
  { ssr: false, loading: () => <div className="flex h-full items-center justify-center text-muted-foreground">Loading graph...</div> }
);

const BFOBucketFilters = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.BFOBucketFilters),
  { ssr: false }
);

export default function OntologyPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams?.toString() || '';
  const { workspaceId: routeWorkspaceId } = useParams<{ workspaceId: string }>();
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const refresh = useOntologyStore(state => state.graphRefreshTrigger);
  const dictionary = useOntologyDictionaryStore();
  const { load } = dictionary;
  const loadIcons = useOntologyIconsStore(state => state.load);
  useEffect(() => {
    if (!workspaceId) return;
    void loadIcons(workspaceId, true);
    const sync = () => { if (document.visibilityState !== 'hidden') void loadIcons(workspaceId, true); };
    window.addEventListener('focus', sync);
    return () => window.removeEventListener('focus', sync);
  }, [workspaceId, refresh, loadIcons]);

  const dictionaryMode = ontologyBrowser(query) === 'dictionary';
  const selectedOntologyPath = dictionaryMode ? null : searchParams?.get('ontology') || null;
  const requestedView = searchParams?.get('view') || (dictionaryMode ? 'overview' : 'network');
  const legacyKind = searchParams?.get('termType') as DictionaryTerm['type'];
  const view = requestedView === 'dictionary' || requestedView === 'editor'
    ? termViews[legacyKind] || 'classes' : requestedView;
  const kind = kindForView(view);
  const requestedTermId = searchParams?.get('term');
  const showDashboard = view === 'overview' || Boolean(kind && !requestedTermId);
  const workspaceTerms = dictionary.workspaceId === workspaceId ? dictionary.terms : [];
  const focusTerm = workspaceTerms.find(term => term.id === requestedTermId && term.type === legacyKind);
  const [queryText, setQueryText] = useState('');
  useEffect(() => {
    if (workspaceId) {
      const pending = useOntologyDictionaryStore.getState().loading;
      void load(workspaceId, refresh, view === 'system' && !pending);
    }
  }, [workspaceId, refresh, load, view]);
  useEffect(() => {
    const next = query ? normalizeOntologyRoute(query) : lastOntologyRoute(routeWorkspaceId);
    if (view !== requestedView) {
      router.replace(`?${viewRoute(next.toString(), view)}`, { scroll: false });
    } else if (next.toString() !== query) {
      router.replace(`?${next}`, { scroll: false });
    } else {
      rememberOntologyRoute(routeWorkspaceId, query);
    }
  }, [query, requestedView, routeWorkspaceId, router, view]);
  const terms = useMemo(() => dictionary.workspaceId === workspaceId
    ? dictionary.terms.filter(term => !selectedOntologyPath || term.sources?.some(source => source.path === selectedOntologyPath))
    : [], [dictionary.workspaceId, dictionary.terms, workspaceId, selectedOntologyPath]);
  const matches = terms.filter(term => term.type === kind && `${term.name} ${term.description || ''}`.toLowerCase().includes(queryText.trim().toLowerCase()));
  const navigate = (next: string) => router.push(`?${viewRoute(query, next)}`, { scroll: false });
  const select = (term: DictionaryTerm) => router.push(`?${termRoute(query, term)}`, { scroll: false });
  const [graph, setGraph] = useState<{nodes: OntologyOverviewGraphNode[]; edges: OntologyOverviewGraphEdge[]; prefixes: Record<string, string>}>({nodes: [], edges: [], prefixes: {}});
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  useEffect(() => {
    if (view !== 'network' || !workspaceId || requestedTermId) return;
    let cancelled = false;
    setGraph({nodes: [], edges: [], prefixes: {}});
    setLoadingGraph(true); setGraphError(null);
    void (async () => {
      try {
        const response = await authFetch(`${getApiUrl()}/api/ontology/overview/graph${ontologyApiQuery({ ontology_path: selectedOntologyPath })}`);
        if (!response.ok) throw new Error('Could not load the ontology graph.');
        const data = await response.json();
        if (!cancelled) setGraph({nodes: data.nodes || [], edges: data.edges || [], prefixes: data.prefixes || {}});
      } catch (error) {
        if (!cancelled) setGraphError(error instanceof Error ? error.message : 'Could not load the ontology graph.');
      } finally { if (!cancelled) setLoadingGraph(false); }
    })();
    return () => { cancelled = true; };
  }, [view, selectedOntologyPath, workspaceId, refresh, requestedTermId]);
  return <div className="flex h-full flex-col overflow-hidden">
    <Header title="Ontology" nav={<OntologyMenuBar />} />
    {view !== 'system' && !showDashboard && <><nav aria-label="Ontology views" className="flex min-h-10 shrink-0 flex-wrap items-center gap-1 border-b bg-muted/30 px-4 py-1">
      {(dictionaryMode ? [['details', 'Details'], ['network', 'Network']] : [['network', 'Network'], ...termTabs]).map(([value, label]) =>
        <button key={value} type="button" aria-current={view === value || (value === 'details' && kind) ? 'page' : undefined} onClick={() => navigate(value)}
          className={cn('rounded-md px-3 py-1 text-[13px]', view === value || (value === 'details' && kind) ? 'bg-background text-foreground' : 'text-muted-foreground hover:bg-background')}>{label}</button>)}
    </nav>
    <div className="shrink-0 truncate border-b px-5 py-2 text-xs text-muted-foreground" title={selectedOntologyPath || undefined}>
      {view === 'network' && requestedTermId ? 'Connections across workspace ontology files' : selectedOntologyPath ? selectedOntologyPath.split('/').pop() : 'All workspace ontology files'}
      {view === 'network' && !selectedOntologyPath && !requestedTermId ? ' · File imports' : ''}
    </div>
    </>}
    <div className="flex min-h-0 flex-1 overflow-hidden">
      {showDashboard ? <OntologyDashboard /> : view === 'system' ? <OntologySystemView terms={workspaceTerms} loading={dictionary.loading || dictionary.workspaceId !== workspaceId} error={dictionary.error} partial={dictionary.errors.length > 0} />
        : view === 'network' && requestedTermId ? dictionary.loading || dictionary.workspaceId !== workspaceId ? <p className="p-5 text-sm text-muted-foreground" role="status">Loading term connections…</p>
        : dictionary.error ? <p className="p-5 text-sm text-destructive" role="alert">{dictionary.error}</p>
        : focusTerm ? <div className="flex min-w-0 flex-1 flex-col">{!!dictionary.errors.length && <p className="border-b px-5 py-2 text-xs text-destructive">Some workspace files could not be read. Connections may be incomplete.</p>}<OntologyTermNetwork key={`${workspaceId}:${focusTerm.type}:${focusTerm.id}`} term={focusTerm} terms={workspaceTerms} /></div>
        : <p className="p-5 text-sm text-muted-foreground">This term is not available in this workspace.</p>
        : view === 'network' ? <OntologyNetworkView key={`${workspaceId}:${selectedOntologyPath || 'all'}:${refresh}`} ontologyPath={selectedOntologyPath}
        graphNodes={graph.nodes} graphEdges={graph.edges} graphPrefixes={graph.prefixes} loadingGraph={loadingGraph} graphError={graphError} />
        : kind ? <>
          {!dictionaryMode && <aside className="w-64 shrink-0 overflow-auto border-r p-3 lg:w-72">
            <input aria-label="Search terms and definitions" placeholder="Search terms…" value={queryText} onChange={event => setQueryText(event.target.value)} className="mb-3 w-full rounded border bg-background px-2 py-2 text-xs" />
            {matches.map(term => <button key={`${term.type}:${term.id}`} type="button" onClick={() => select(term)} title={term.id}
              aria-current={searchParams?.get('term') === term.id && searchParams?.get('termType') === term.type ? 'page' : undefined}
              className={cn('block w-full truncate rounded px-2 py-1 text-left text-[13px] leading-5 hover:bg-muted', searchParams?.get('term') === term.id && searchParams?.get('termType') === term.type && 'bg-workspace-accent-10 text-workspace-accent')}>{term.name}</button>)}
            {!dictionary.loading && !dictionary.error && !matches.length && <p className="text-xs text-muted-foreground">No matching terms in this scope.</p>}
          </aside>}
          <OntologyDictionaryEntry />
        </> : <div className="p-5 text-sm text-muted-foreground">Ontology file editing is not available in this view. <button type="button" onClick={() => navigate('classes')} className="text-workspace-accent hover:underline">Browse classes</button></div>}
    </div>
  </div>;
}

function compactUri(iri: string, prefixes: Record<string, string>): string {
  for (const [prefix, ns] of Object.entries(prefixes)) {
    if (iri.startsWith(ns)) return `${prefix}:${iri.slice(ns.length)}`;
  }
  return iri;
}

// BFO bucket resolution helpers (mirrors vis-network.tsx, no browser deps)
const BFO_BUCKET_KEYS = new Set([
  'Material Entity',
  'Process',
  'Temporal Region',
  'Site',
  'Quality',
  'Realizable',
  'GDC',
  'Entity',
]);

const BFO_URI_TO_BUCKET_LOCAL: Record<string, string> = {
  'http://purl.obolibrary.org/obo/BFO_0000040': 'Material Entity',
  'http://purl.obolibrary.org/obo/BFO_0000015': 'Process',
  'http://purl.obolibrary.org/obo/BFO_0000008': 'Temporal Region',
  'http://purl.obolibrary.org/obo/BFO_0000029': 'Site',
  'http://purl.obolibrary.org/obo/BFO_0000031': 'GDC',
  'http://purl.obolibrary.org/obo/BFO_0000019': 'Quality',
  'http://purl.obolibrary.org/obo/BFO_0000017': 'Realizable',
  'BFO_0000040': 'Material Entity',
  'BFO_0000015': 'Process',
  'BFO_0000008': 'Temporal Region',
  'BFO_0000029': 'Site',
  'BFO_0000031': 'GDC',
  'BFO_0000019': 'Quality',
  'BFO_0000017': 'Realizable',
};

const LABEL_TO_BUCKET_LOCAL: Record<string, string> = {
  'material entity': 'Material Entity',
  'object': 'Material Entity',
  'object aggregate': 'Material Entity',
  'fiat object part': 'Material Entity',
  'independent continuant': 'Material Entity',
  'process': 'Process',
  'occurrent': 'Process',
  'process boundary': 'Process',
  'temporal region': 'Temporal Region',
  'temporal interval': 'Temporal Region',
  'zero-dimensional temporal region': 'Temporal Region',
  'one-dimensional temporal region': 'Temporal Region',
  'site': 'Site',
  'immaterial entity': 'Site',
  'spatial region': 'Site',
  'continuant fiat boundary': 'Site',
  'quality': 'Quality',
  'specifically dependent continuant': 'Quality',
  'role': 'Realizable',
  'disposition': 'Realizable',
  'realizable entity': 'Realizable',
  'generically dependent continuant': 'GDC',
  'entity': 'Entity',
};

function resolveNodeBucket(node: OntologyOverviewGraphNode, nodesById?: Map<string, OntologyOverviewGraphNode>, visited: Set<string> = new Set()): string | null {
  const bfoParentIri = node.properties?.bfo_parent_iri as string | undefined;
  if (bfoParentIri && bfoParentIri in BFO_URI_TO_BUCKET_LOCAL) return BFO_URI_TO_BUCKET_LOCAL[bfoParentIri];
  if (BFO_BUCKET_KEYS.has(node.type)) return node.type;
  const lowerType = node.type?.toLowerCase?.() ?? '';
  if (lowerType in LABEL_TO_BUCKET_LOCAL) return LABEL_TO_BUCKET_LOCAL[lowerType];
  if (node.type in BFO_URI_TO_BUCKET_LOCAL) return BFO_URI_TO_BUCKET_LOCAL[node.type];
  const parentIri = node.properties?.parent_iri as string | undefined;
  if (parentIri && parentIri in BFO_URI_TO_BUCKET_LOCAL) return BFO_URI_TO_BUCKET_LOCAL[parentIri];

  if (nodesById && parentIri && !visited.has(node.id)) {
    visited.add(node.id);
    const parentNode = nodesById.get(parentIri);
    if (parentNode) return resolveNodeBucket(parentNode, nodesById, visited);
  }

  return null;
}

function OntologyNetworkView({
  ontologyPath,
  graphNodes,
  graphEdges,
  graphPrefixes,
  loadingGraph,
  graphError,
}: {
  ontologyPath: string | null;
  graphNodes: OntologyOverviewGraphNode[];
  graphEdges: OntologyOverviewGraphEdge[];
  graphPrefixes: Record<string, string>;
  loadingGraph: boolean;
  graphError: string | null;
}) {
  const searchParams = useSearchParams();
  const spacing = ontologySpacing(searchParams?.toString() || '');
  const [graphSearchQuery, setGraphSearchQuery] = useState('');
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null);
  const [selectedGraphEdgeId, setSelectedGraphEdgeId] = useState<string | null>(null);
  const [subclassOfEnabled, setSubclassOfEnabled] = useState(false);
  // Number of *top* levels hidden (top-down filter). 0 = show everything.
  const [subclassOfHiddenTopLevels, setSubclassOfHiddenTopLevels] = useState(0);
  const [loadingSubclassOfHierarchy, setLoadingSubclassOfHierarchy] = useState(false);
  // Full hierarchy, grouped by computed "level" (BFO entity = level 1, otherwise highest parent = level 1).
  const [hierarchyByLevel, setHierarchyByLevel] = useState<Array<{
    level: number;
    nodes: OntologyOverviewGraphNode[];
    edges: OntologyOverviewGraphEdge[];
  }>>([]);
  const [showRestrictions, setShowRestrictions] = useState(false);
  const [showObjectProperties, setShowObjectProperties] = useState(false);
  const [layoutDirection, setLayoutDirection] = useState<'TD' | 'LR'>('TD');
  // BFO bucket filters — empty = no filter (show all)
  const [activeBuckets, setActiveBuckets] = useState<Set<string>>(new Set());
  /** When set, graph shows only this node (still respects search + bucket + relation toggles). */
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  /** Per-node visibility overrides — nodes in this set are hidden from the graph. */
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());
  const isAllOntologiesOverview = !ontologyPath;

  /** Persist vis-network zoom/pan per relation / SubclassOf mode. */
  const ontologyGraphViewStateKey = useMemo(() => {
    if (isAllOntologiesOverview) return 'ontology:imports-overview';
    const subPart = subclassOfEnabled
      ? `sub:on:${layoutDirection}:hide${subclassOfHiddenTopLevels}`
      : 'sub:off';
    return `ontology:class|${subPart}|r:${showRestrictions}|op:${showObjectProperties}`;
  }, [
    isAllOntologiesOverview,
    subclassOfEnabled,
    layoutDirection,
    subclassOfHiddenTopLevels,
    showRestrictions,
    showObjectProperties,
  ]);

  /**
   * Live force-directed physics is on whenever Restrictions or Object Properties
   * filters are active — those edge sets benefit from a self-organising layout.
   * Persisted per `(ontology, filters)` context so navigating back to the same
   * view restores the same physics state.
   */
  const physicsByContextRef = useRef(new Map<string, boolean>());
  const physicsEnabled = useMemo(
    () => showRestrictions || showObjectProperties,
    [showRestrictions, showObjectProperties]
  );
  useEffect(() => {
    physicsByContextRef.current.set(ontologyGraphViewStateKey, physicsEnabled);
  }, [ontologyGraphViewStateKey, physicsEnabled]);

  const getNodeTitle = useCallback((node: OntologyOverviewGraphNode) => {
    const subclassOf = String(node.properties?.parent_label || node.properties?.parent_iri || '—');
    const rawDef = String(node.properties?.definition || '—');
    const definition = rawDef.length > 200 ? rawDef.slice(0, 200) + '…' : rawDef;
    return buildHoverTitle([
      ['uri', compactUri(node.id, graphPrefixes)],
      ['label', node.label],
      ['subclassOf', subclassOf],
      ['definition', definition],
    ]);
  }, [graphPrefixes]);

  const handleBucketToggle = useCallback((bucketType: string) => {
    setActiveBuckets((prev) => {
      const next = new Set(prev);
      if (next.has(bucketType)) {
        next.delete(bucketType);
      } else {
        next.add(bucketType);
      }
      return next;
    });
  }, []);

  const handleNodeToggle = useCallback((nodeId: string) => {
    setHiddenNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const totalSubclassOfLevels = useMemo(() => hierarchyByLevel.length, [hierarchyByLevel.length]);
  const visibleSubclassOfMinLevel = useMemo(
    () => 1 + Math.min(subclassOfHiddenTopLevels, Math.max(0, totalSubclassOfLevels - 1)),
    [subclassOfHiddenTopLevels, totalSubclassOfLevels]
  );

  const visibleHierarchyLevels = useMemo(() => {
    if (!subclassOfEnabled) return [];
    return hierarchyByLevel.filter((lvl) => lvl.level >= visibleSubclassOfMinLevel);
  }, [hierarchyByLevel, subclassOfEnabled, visibleSubclassOfMinLevel]);

  // Combined nodes: initial + full hierarchy (filtered top-down)
  const allVisibleNodes = useMemo(() => {
    if (!subclassOfEnabled) return graphNodes;
    const result = [...graphNodes];
    const seen = new Set(result.map((n) => n.id));
    for (const level of visibleHierarchyLevels) {
      for (const node of level.nodes) {
        if (!seen.has(node.id)) {
          result.push(node);
          seen.add(node.id);
        }
      }
    }
    return result;
  }, [graphNodes, subclassOfEnabled, visibleHierarchyLevels]);

  const nodesByIri = useMemo(() => {
    const map = new Map<string, OntologyOverviewGraphNode>();
    for (const n of allVisibleNodes) map.set(n.id, n);
    return map;
  }, [allVisibleNodes]);

  const nodeLevelById = useMemo(() => {
    const map = new Map<string, number>();
    for (const lvl of hierarchyByLevel) {
      for (const n of lvl.nodes) map.set(n.id, lvl.level);
    }
    return map;
  }, [hierarchyByLevel]);

  const nodesMatchingSearchAndBuckets = useMemo(() => {
    let nodes = allVisibleNodes;

    if (graphSearchQuery.trim()) {
      const query = graphSearchQuery.toLowerCase();
      nodes = nodes.filter(
        (node) =>
          node.label.toLowerCase().includes(query) ||
          node.id.toLowerCase().includes(query) ||
          node.type.toLowerCase().includes(query)
      );
    }

    if (activeBuckets.size > 0) {
      nodes = nodes.filter((node) => {
        const bucket = resolveNodeBucket(node, nodesByIri);
        if (bucket === null) return activeBuckets.has('Unknown');
        return activeBuckets.has(bucket);
      });
    }

    return nodes;
  }, [allVisibleNodes, nodesByIri, graphSearchQuery, activeBuckets]);

  // When any relation filter is active, expand the visible set with neighbor nodes reachable via
  // those relation edges. In focus mode: focused node + its neighbors. Outside focus: all filtered
  // nodes + their neighbors. Covers SubclassOf, Restrictions, and Object Properties.
  const expandedNodes = useMemo(() => {
    const baseNodes = focusedNodeId
      ? nodesMatchingSearchAndBuckets.filter((n) => n.id === focusedNodeId)
      : nodesMatchingSearchAndBuckets;

    // Collect every edge that is currently active across all three relation toggles.
    const activeRelEdges: OntologyOverviewGraphEdge[] = [];

    if (showRestrictions) {
      for (const e of graphEdges) {
        if (e.properties?.relation_kind === 'restriction') activeRelEdges.push(e);
      }
    }
    if (showObjectProperties) {
      for (const e of graphEdges) {
        if (e.properties?.relation_kind === 'object_property') activeRelEdges.push(e);
      }
    }
    if (subclassOfEnabled) {
      for (const level of visibleHierarchyLevels) {
        for (const e of level.edges) activeRelEdges.push(e);
      }
    }

    if (activeRelEdges.length === 0) return baseNodes;

    const baseIds = new Set(baseNodes.map((n) => n.id));
    const toAdd = new Set<string>();
    for (const edge of activeRelEdges) {
      if (baseIds.has(edge.source) && !baseIds.has(edge.target)) toAdd.add(edge.target);
      if (baseIds.has(edge.target) && !baseIds.has(edge.source)) toAdd.add(edge.source);
    }

    if (toAdd.size === 0) return baseNodes;

    const extras = Array.from(toAdd)
      .map((id) => nodesByIri.get(id))
      .filter((n): n is OntologyOverviewGraphNode => n !== undefined);

    return [...baseNodes, ...extras];
  }, [nodesMatchingSearchAndBuckets, focusedNodeId, showRestrictions, showObjectProperties, subclassOfEnabled, visibleHierarchyLevels, graphEdges, nodesByIri]);

  const nodesAfterLevelFilter = useMemo(() => {
    if (!subclassOfEnabled) return expandedNodes;
    return expandedNodes.filter((n) => {
      const lvl = nodeLevelById.get(n.id);
      // If we can't compute a level (missing edges), keep the node visible.
      if (lvl === undefined) return true;
      return lvl >= visibleSubclassOfMinLevel;
    });
  }, [expandedNodes, nodeLevelById, subclassOfEnabled, visibleSubclassOfMinLevel]);

  // Effective active buckets: user-selected + auto-activated buckets for relation-expanded nodes.
  const effectiveActiveBuckets = useMemo(() => {
    if (activeBuckets.size === 0) return activeBuckets;
    const result = new Set(activeBuckets);
    for (const node of nodesAfterLevelFilter) {
      const b = resolveNodeBucket(node, nodesByIri);
      if (b) result.add(b);
    }
    return result;
  }, [activeBuckets, nodesAfterLevelFilter, nodesByIri]);

  // Nodes grouped by bucket for the BFO panel checkboxes.
  const nodesPerBucketForPanel = useMemo(() => {
    const map = new Map<string, Array<{ id: string; label: string }>>();
    for (const node of nodesAfterLevelFilter) {
      const bucket = resolveNodeBucket(node, nodesByIri) ?? 'Unknown';
      const existing = map.get(bucket) ?? [];
      existing.push({ id: node.id, label: node.label });
      map.set(bucket, existing);
    }
    for (const [, nodes] of map) {
      nodes.sort((a, b) => a.label.localeCompare(b.label));
    }
    return map;
  }, [nodesAfterLevelFilter, nodesByIri]);

  const filteredGraphNodes = useMemo(() => {
    return nodesAfterLevelFilter.filter((n) => !hiddenNodeIds.has(n.id));
  }, [nodesAfterLevelFilter, hiddenNodeIds]);

  useEffect(() => {
    if (!focusedNodeId) return;
    if (
      !nodesMatchingSearchAndBuckets.some((n) => n.id === focusedNodeId) ||
      hiddenNodeIds.has(focusedNodeId)
    ) {
      setFocusedNodeId(null);
    }
  }, [focusedNodeId, nodesMatchingSearchAndBuckets, hiddenNodeIds]);

  const filteredGraphEdges = useMemo(() => {
    const importEdges = graphEdges.filter((e) => e.properties?.relation_kind === 'imports');
    const restrictionEdges = graphEdges.filter((e) => e.properties?.relation_kind === 'restriction');
    const objectPropEdges = graphEdges.filter((e) => e.properties?.relation_kind === 'object_property');

    let baseEdges: OntologyOverviewGraphEdge[] = [...importEdges];

    if (subclassOfEnabled) {
      for (const level of visibleHierarchyLevels) {
        baseEdges = [...baseEdges, ...level.edges];
      }
    }

    if (showRestrictions) baseEdges = [...baseEdges, ...restrictionEdges];
    if (showObjectProperties) baseEdges = [...baseEdges, ...objectPropEdges];

    const needsNodeMask =
      Boolean(graphSearchQuery.trim()) || activeBuckets.size > 0 || Boolean(focusedNodeId) || hiddenNodeIds.size > 0 || showRestrictions || showObjectProperties;
    if (!needsNodeMask) return baseEdges;
    const visibleNodeIds = new Set(filteredGraphNodes.map((node) => node.id));
    return baseEdges.filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target));
  }, [
    graphEdges,
    filteredGraphNodes,
    graphSearchQuery,
    activeBuckets,
    focusedNodeId,
    hiddenNodeIds,
    subclassOfEnabled,
    visibleHierarchyLevels,
    showRestrictions,
    showObjectProperties,
  ]);

  const subclassOfFrontierForHierarchy = useMemo(() => {
    if (focusedNodeId) {
      const node = nodesByIri.get(focusedNodeId);
      return node ? [node] : [];
    }

    if (!graphSearchQuery.trim() && activeBuckets.size === 0) {
      return graphNodes.filter((n) => n.properties?.is_primary === true);
    }

    const baseMap = new Map(graphNodes.map((n) => [n.id, n]));
    let nodes = graphNodes;
    if (graphSearchQuery.trim()) {
      const q = graphSearchQuery.toLowerCase();
      nodes = nodes.filter(
        (n) =>
          n.label.toLowerCase().includes(q) ||
          n.id.toLowerCase().includes(q) ||
          n.type.toLowerCase().includes(q)
      );
    }
    if (activeBuckets.size > 0) {
      nodes = nodes.filter((n) => {
        const bucket = resolveNodeBucket(n, baseMap);
        return bucket !== null ? activeBuckets.has(bucket) : activeBuckets.has('Unknown');
      });
    }
    return nodes;
  }, [focusedNodeId, graphSearchQuery, activeBuckets, graphNodes, nodesByIri]);

  const subclassOfFrontierKey = useMemo(
    () => subclassOfFrontierForHierarchy.map((n) => n.id).sort().join(','),
    [subclassOfFrontierForHierarchy]
  );

  // When the frontier changes, discard the computed hierarchy.
  const prevFrontierKeyRef = useRef<string | null>(null);
  useEffect(() => {
    if (prevFrontierKeyRef.current === null) {
      prevFrontierKeyRef.current = subclassOfFrontierKey;
      return;
    }
    if (prevFrontierKeyRef.current !== subclassOfFrontierKey) {
      prevFrontierKeyRef.current = subclassOfFrontierKey;
      setSubclassOfEnabled(false);
      setSubclassOfHiddenTopLevels(0);
      setHierarchyByLevel([]);
    }
  }, [subclassOfFrontierKey]);

  const fetchAndComputeFullSubclassOfHierarchy = useCallback(async () => {
    if (!ontologyPath || loadingSubclassOfHierarchy) return;
    if (subclassOfFrontierForHierarchy.length === 0) {
      setHierarchyByLevel([]);
      setSubclassOfHiddenTopLevels(0);
      setSubclassOfEnabled(true);
      return;
    }
    setLoadingSubclassOfHierarchy(true);
    try {
      const baseUrl = getApiUrl();
      const params = ontologyApiParams({ ontology_path: ontologyPath });
      subclassOfFrontierForHierarchy.forEach((n) => params.append('class_iris', n.id));

      const response = await authFetch(`${baseUrl}/api/ontology/overview/hierarchy?${params.toString()}`);
      if (!response.ok) return;

      const data = (await response.json()) as {
        nodes?: OntologyOverviewGraphNode[];
        edges?: OntologyOverviewGraphEdge[];
      };
      const nodes = Array.isArray(data.nodes) ? data.nodes : [];
      const edges = Array.isArray(data.edges) ? data.edges : [];

      // Group by precomputed level (set by the backend on each node).
      const nodesByLevel = new Map<number, OntologyOverviewGraphNode[]>();
      for (const n of nodes) {
        const lvl = typeof n.properties?.level === 'number' ? (n.properties.level as number) : 1;
        const arr = nodesByLevel.get(lvl) ?? [];
        arr.push(n);
        nodesByLevel.set(lvl, arr);
      }
      for (const arr of nodesByLevel.values()) {
        arr.sort((a, b) => a.label.localeCompare(b.label));
      }

      // Edges keyed by source-node level (matches previous client-side grouping).
      const levelById = new Map<string, number>();
      for (const n of nodes) {
        const lvl = typeof n.properties?.level === 'number' ? (n.properties.level as number) : 1;
        levelById.set(n.id, lvl);
      }
      const edgesByLevel = new Map<number, OntologyOverviewGraphEdge[]>();
      for (const e of edges) {
        if (e.properties?.relation_kind !== 'is_a') continue;
        const srcLvl = levelById.get(e.source);
        if (srcLvl === undefined) continue;
        const arr = edgesByLevel.get(srcLvl) ?? [];
        arr.push(e);
        edgesByLevel.set(srcLvl, arr);
      }

      const maxLevel = nodes.length > 0
        ? Math.max(...Array.from(levelById.values()))
        : 0;
      const hierarchy: Array<{
        level: number;
        nodes: OntologyOverviewGraphNode[];
        edges: OntologyOverviewGraphEdge[];
      }> = [];
      for (let lvl = 1; lvl <= maxLevel; lvl++) {
        hierarchy.push({
          level: lvl,
          nodes: nodesByLevel.get(lvl) ?? [],
          edges: edgesByLevel.get(lvl) ?? [],
        });
      }

      setHierarchyByLevel(hierarchy);
      setSubclassOfHiddenTopLevels(0);
      setSubclassOfEnabled(true);
    } catch (err) {
      console.error('Failed to fetch full SubclassOf hierarchy:', err);
    } finally {
      setLoadingSubclassOfHierarchy(false);
    }
  }, [
    ontologyPath,
    loadingSubclassOfHierarchy,
    subclassOfFrontierForHierarchy,
  ]);

  // Auto-expand the first subclassOf level once the graph finishes loading (loadingGraph: true → false).
  // Resets per ontology so switching ontologies re-applies the hierarchical view.
  const didAutoExpandRef = useRef(false);
  const wasLoadingRef = useRef(false);
  const autoExpandedForPathRef = useRef<string | null>(null);
  useEffect(() => {
    if (autoExpandedForPathRef.current !== ontologyPath) {
      didAutoExpandRef.current = false;
      autoExpandedForPathRef.current = ontologyPath;
    }
  }, [ontologyPath]);
  useEffect(() => {
    if (loadingGraph) {
      wasLoadingRef.current = true;
      return;
    }
    if (!wasLoadingRef.current) return;
    wasLoadingRef.current = false;
    if (didAutoExpandRef.current) return;
    if (!ontologyPath || graphNodes.length === 0) return;
    didAutoExpandRef.current = true;
    fetchAndComputeFullSubclassOfHierarchy();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ontologyPath, loadingGraph, graphNodes.length]);

  const graphNodesById = useMemo(
    () => new Map(allVisibleNodes.map((node) => [node.id, node])),
    [allVisibleNodes]
  );
  const selectedGraphNode = selectedGraphNodeId ? graphNodesById.get(selectedGraphNodeId) : null;
  const selectedGraphNodeLevel = useMemo(() => {
    if (!selectedGraphNode) return null;
    const computed = nodeLevelById.get(selectedGraphNode.id);
    if (computed !== undefined) return computed;
    return null;
  }, [selectedGraphNode, nodeLevelById]);
  const selectedGraphNodeIsOntology = selectedGraphNode?.type === 'Ontology';
  const selectedGraphNodeDescription =
    selectedGraphNode?.properties?.comment ||
    selectedGraphNode?.properties?.description ||
    (selectedGraphNodeIsOntology ? 'No comment' : 'No definition');
  const selectedGraphEdge = selectedGraphEdgeId
    ? graphEdges.find((edge) => edge.id === selectedGraphEdgeId) || null
    : null;

  return (
    <div className="flex min-h-full flex-1 flex-col overflow-hidden bg-card">
      <div className="flex flex-1 overflow-hidden">
        <div className="relative flex flex-1 flex-col bg-zinc-50 dark:bg-zinc-900">
          <div className="absolute left-4 top-4 z-10 flex gap-2">
            <div className="flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5 shadow-sm">
              <Search size={14} className="text-muted-foreground" />
              <input
                type="text"
                value={graphSearchQuery}
                onChange={(e) => setGraphSearchQuery(e.target.value)}
                placeholder={isAllOntologiesOverview ? 'Search ontologies...' : 'Search classes...'}
                className="w-52 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              {graphSearchQuery && (
                <button
                  onClick={() => setGraphSearchQuery('')}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X size={14} />
                </button>
              )}
            </div>
            {!isAllOntologiesOverview && (
              <>
                <div className="flex items-center rounded-lg border bg-card shadow-sm overflow-hidden">
                  <button
                    onClick={() => {
                      if (!subclassOfEnabled) {
                        fetchAndComputeFullSubclassOfHierarchy();
                        return;
                      }
                      setSubclassOfEnabled(false);
                      setSubclassOfHiddenTopLevels(0);
                    }}
                    title={subclassOfEnabled ? "Hide SubclassOf hierarchy" : "Show full SubclassOf hierarchy (rdfs:subClassOf)"}
                    disabled={loadingSubclassOfHierarchy}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-1.5 text-xs',
                      subclassOfEnabled
                        ? 'bg-foreground text-background'
                        : 'text-muted-foreground hover:text-foreground',
                      loadingSubclassOfHierarchy && 'opacity-60 cursor-not-allowed'
                    )}
                  >
                    {loadingSubclassOfHierarchy ? <Loader2 size={12} className="animate-spin" /> : <GitBranch size={12} />}
                    SubclassOf{subclassOfEnabled && totalSubclassOfLevels > 0 && ` (${totalSubclassOfLevels - subclassOfHiddenTopLevels})`}
                  </button>
                  {subclassOfEnabled && totalSubclassOfLevels > 1 && (
                    <button
                      onClick={() =>
                        setSubclassOfHiddenTopLevels((v) =>
                          Math.min(totalSubclassOfLevels - 1, v + 1)
                        )
                      }
                      title="Hide top level (−1)"
                      disabled={loadingSubclassOfHierarchy || subclassOfHiddenTopLevels >= totalSubclassOfLevels - 1}
                      className="border-l px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60"
                    >
                      −
                    </button>
                  )}
                  {subclassOfEnabled && totalSubclassOfLevels > 1 && (
                    <button
                      onClick={() => setSubclassOfHiddenTopLevels((v) => Math.max(0, v - 1))}
                      title="Show one more top level (+1)"
                      disabled={loadingSubclassOfHierarchy || subclassOfHiddenTopLevels === 0}
                      className="border-l px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      +
                    </button>
                  )}
                </div>
                {subclassOfEnabled && (
                  <div className="flex items-center rounded-lg border bg-card shadow-sm overflow-hidden">
                    <button
                      onClick={() => setLayoutDirection('TD')}
                      title="Top-down hierarchy (entity on top)"
                      className={cn(
                        'border-l px-3 py-1.5 text-xs',
                        layoutDirection === 'TD'
                          ? 'bg-foreground text-background'
                          : 'text-muted-foreground hover:text-foreground',
                      )}
                    >
                      TD
                    </button>
                    <button
                      onClick={() => setLayoutDirection('LR')}
                      title="Left-to-right hierarchy (entity on left)"
                      className={cn(
                        'px-3 py-1.5 text-xs',
                        layoutDirection === 'LR'
                          ? 'bg-foreground text-background'
                          : 'text-muted-foreground hover:text-foreground',
                      )}
                    >
                      LR
                    </button>
                  </div>
                )}
                <button
                  onClick={() => setShowRestrictions((v) => !v)}
                  title="Toggle OWL Restrictions (owl:Restriction)"
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs shadow-sm',
                    showRestrictions
                      ? 'border-foreground bg-foreground text-background'
                      : 'border-border bg-card text-muted-foreground hover:text-foreground'
                  )}
                >
                  <AlertCircle size={12} />
                  Restrictions
                </button>
                <button
                  onClick={() => setShowObjectProperties((v) => !v)}
                  title="Toggle Object Properties (rdfs:domain / rdfs:range)"
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs shadow-sm',
                    showObjectProperties
                      ? 'border-foreground bg-foreground text-background'
                      : 'border-border bg-card text-muted-foreground hover:text-foreground'
                  )}
                >
                  <ArrowRight size={12} />
                  Object Properties
                </button>
              </>
            )}
            {(graphSearchQuery.trim() || activeBuckets.size > 0 || focusedNodeId || hiddenNodeIds.size > 0) && (
              <span className="flex items-center rounded-lg border bg-card/80 px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
                Showing {filteredGraphNodes.length} of{' '}
                {expandedNodes.length}{' '}
                {isAllOntologiesOverview ? 'ontologies' : 'classes'}
                {focusedNodeId ? ' (focused)' : ''}
                {hiddenNodeIds.size > 0 ? ` · ${hiddenNodeIds.size} hidden` : ''}
              </span>
            )}
          </div>

          {!isAllOntologiesOverview && (
            <BFOBucketFilters
              activeBuckets={activeBuckets}
              effectiveActiveBuckets={effectiveActiveBuckets}
              onToggle={handleBucketToggle}
              nodesPerBucket={nodesPerBucketForPanel}
              hiddenNodeIds={hiddenNodeIds}
              onNodeToggle={handleNodeToggle}
            />
          )}

          {loadingGraph ? (
            <div className="flex h-full items-center justify-center gap-2 text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              Loading ontology graph...
            </div>
          ) : graphError ? (
            <div className="flex h-full items-center justify-center px-6">
              <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300">
                {graphError}
              </div>
            </div>
          ) : filteredGraphNodes.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {isAllOntologiesOverview ? 'No ontologies found for this selection.' : 'No classes found for this ontology.'}
            </div>
          ) : (
            <VisNetwork
              zoomOnDoubleClick
              spacingKey={spacing.value}
              minimumAutoFitScale={1}
              nodeSpacing={spacing.gap}
              orthogonalEdges={searchParams?.get('connectors') !== 'curved'}
              nodes={filteredGraphNodes}
              edges={filteredGraphEdges}
              selectedNodeId={selectedGraphNodeId}
              onNodeSelect={(nodeId) => {
                setSelectedGraphNodeId(nodeId);
                setSelectedGraphEdgeId(null);
              }}
              onEdgeSelect={(edgeId) => {
                setSelectedGraphEdgeId(edgeId);
                if (edgeId) setSelectedGraphNodeId(null);
              }}
              layoutDirection={subclassOfEnabled ? layoutDirection : undefined}
              viewStateKey={ontologyGraphViewStateKey}
              physicsEnabled={physicsEnabled}
              getNodeTitle={getNodeTitle}
            />
          )}
        </div>

        {(selectedGraphNode || selectedGraphEdge) && (
          <div className="w-80 flex-shrink-0 border-l bg-card">
            <div className="flex h-10 items-center justify-between border-b px-4">
              <span className="text-sm font-medium">Inspector</span>
              <button
                onClick={() => {
                  setSelectedGraphNodeId(null);
                  setSelectedGraphEdgeId(null);
                  setFocusedNodeId(null);
                }}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                title="Close inspector"
              >
                <X size={14} />
              </button>
            </div>
            <div className="space-y-4 overflow-y-auto p-4 text-sm">
              {selectedGraphNode && (
                <>
                  <div className="flex items-center gap-2">
                    <Box size={16} className="text-blue-500" />
                    <span className="font-medium">{selectedGraphNode.label}</span>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Type</p>
                    <p>{isAllOntologiesOverview ? 'Ontology' : 'Class'}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">URIRef</p>
                    <p className="break-all font-mono text-xs">
                      {String(selectedGraphNode.properties?.iri || selectedGraphNode.id)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {selectedGraphNodeIsOntology ? 'Comment' : 'Definition'}
                    </p>
                    <p>{String(selectedGraphNodeIsOntology ? selectedGraphNodeDescription : selectedGraphNode.properties?.definition || 'No definition')}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {isAllOntologiesOverview ? 'Version Info' : 'Subclass Of'}
                    </p>
                    <p>
                      {String(
                        isAllOntologiesOverview
                          ? selectedGraphNode.properties?.version_info || 'N/A'
                          : selectedGraphNode.properties?.parent_label || selectedGraphNode.properties?.parent_iri || 'None'
                      )}
                    </p>
                  </div>
                  {isAllOntologiesOverview && (
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Source Path</p>
                    <p className="break-all font-mono text-xs">
                      {String(selectedGraphNode.properties?.source_path || 'N/A')}
                    </p>
                  </div>
                  )}
                  {!isAllOntologiesOverview && (
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">BFO Bucket</p>
                      <p>{resolveNodeBucket(selectedGraphNode, nodesByIri) ?? 'Unknown'}</p>
                    </div>
                  )}
                  {!isAllOntologiesOverview && selectedGraphNodeLevel !== null && (
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Level</p>
                      <p>{selectedGraphNodeLevel}</p>
                    </div>
                  )}
                  <button
                    type="button"
                    disabled={
                      !nodesMatchingSearchAndBuckets.some((n) => n.id === selectedGraphNode.id)
                    }
                    onClick={() => {
                      if (focusedNodeId === selectedGraphNode.id) {
                        setFocusedNodeId(null);
                        return;
                      }
                      setFocusedNodeId(selectedGraphNode.id);
                    }}
                    className={cn(
                      'flex w-full items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                      focusedNodeId === selectedGraphNode.id
                        ? 'border-workspace-accent bg-workspace-accent-10 text-workspace-accent'
                        : 'border-border bg-muted/40 hover:bg-muted',
                      !nodesMatchingSearchAndBuckets.some((n) => n.id === selectedGraphNode.id) &&
                        'cursor-not-allowed opacity-50'
                    )}
                    title={
                      !nodesMatchingSearchAndBuckets.some((n) => n.id === selectedGraphNode.id)
                        ? 'This node is hidden by the current search or BFO filters'
                        : focusedNodeId === selectedGraphNode.id
                          ? 'Show all nodes matching the current filters'
                          : 'Show only this node (same relation toggles and filters)'
                    }
                  >
                    <Focus size={16} />
                    {focusedNodeId === selectedGraphNode.id ? 'Show all nodes' : 'Focus'}
                  </button>
                </>
              )}
              {selectedGraphEdge && (
                <>
                  <div className="flex items-center gap-2">
                    <Link2 size={16} className="text-green-500" />
                    <span className="font-medium">{selectedGraphEdge.label || selectedGraphEdge.type}</span>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Type</p>
                    <p>{isAllOntologiesOverview ? 'Dependency' : 'Relation'}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Kind</p>
                    <p>{String(selectedGraphEdge.properties?.relation_kind || (isAllOntologiesOverview ? 'imports' : 'object_property'))}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">URIRef</p>
                    <p className="break-all font-mono text-xs">
                      {String(selectedGraphEdge.properties?.iri || selectedGraphEdge.id)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {isAllOntologiesOverview ? 'Importer' : 'From'}
                    </p>
                    <p>{graphNodesById.get(selectedGraphEdge.source)?.label || selectedGraphEdge.source}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {isAllOntologiesOverview ? 'Imported Ontology' : 'To'}
                    </p>
                    <p>{graphNodesById.get(selectedGraphEdge.target)?.label || selectedGraphEdge.target}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {isAllOntologiesOverview ? 'Description' : 'Definition'}
                    </p>
                    <p>{String(selectedGraphEdge.properties?.definition || 'No definition')}</p>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
