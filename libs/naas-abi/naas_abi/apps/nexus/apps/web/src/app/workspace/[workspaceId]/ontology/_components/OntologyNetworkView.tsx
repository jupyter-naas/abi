'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  AlertCircle,
  ArrowRight,
  Box,
  Focus,
  GitBranch,
  Link2,
  Loader2,
  Search,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOntologyHierarchy } from '../_hooks/use-ontology-queries';
import { resolveNodeBucket } from './resolveNodeBucket';
import type { OntologyOverviewGraphEdge, OntologyOverviewGraphNode } from './types';

const VisNetwork = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.VisNetwork),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Loading graph...
      </div>
    ),
  },
);

const BFOBucketFilters = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.BFOBucketFilters),
  { ssr: false },
);

export interface OntologyNetworkViewProps {
  ontologyPath: string | null;
  graphNodes: OntologyOverviewGraphNode[];
  graphEdges: OntologyOverviewGraphEdge[];
  loadingGraph: boolean;
  graphError: string | null;
}

export function OntologyNetworkView({
  ontologyPath,
  graphNodes,
  graphEdges,
  loadingGraph,
  graphError,
}: OntologyNetworkViewProps) {
  const [graphSearchQuery, setGraphSearchQuery] = useState('');
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null);
  const [selectedGraphEdgeId, setSelectedGraphEdgeId] = useState<string | null>(null);
  const [subclassOfEnabled, setSubclassOfEnabled] = useState(false);
  // Number of *top* levels hidden (top-down filter). 0 = show everything.
  const [subclassOfHiddenTopLevels, setSubclassOfHiddenTopLevels] = useState(0);
  const [showRestrictions, setShowRestrictions] = useState(false);
  const [showObjectProperties, setShowObjectProperties] = useState(false);
  const [layoutDirection, setLayoutDirection] = useState<'LR' | 'TD'>('LR');
  // BFO bucket filters — empty = no filter (show all)
  const [activeBuckets, setActiveBuckets] = useState<Set<string>>(new Set());
  /** When set, graph shows only this node (still respects search + bucket + relation toggles). */
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  /** Per-node visibility overrides — nodes in this set are hidden from the graph. */
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());
  /** Incremented to trigger a physics re-spread after returning from focus mode. */
  const [graphStabilizeKey, setGraphStabilizeKey] = useState(0);
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
    [showRestrictions, showObjectProperties],
  );
  useEffect(() => {
    physicsByContextRef.current.set(ontologyGraphViewStateKey, physicsEnabled);
  }, [ontologyGraphViewStateKey, physicsEnabled]);

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

  /** Clears focus, closes the inspector, and triggers a physics re-spread of the graph. */
  const handleUnfocus = useCallback(() => {
    setFocusedNodeId(null);
    setSelectedGraphNodeId(null);
    setSelectedGraphEdgeId(null);
    setGraphStabilizeKey((k) => k + 1);
  }, []);

  /* ─────────────────────── SubclassOf hierarchy ───────────────────────
   * Driven entirely by TanStack Query: the user-visible toggle just flips
   * `subclassOfEnabled` and the query refetches when its (ontologyPath,
   * frontier) key changes. The grouped-by-level shape is computed once
   * via useMemo so downstream rendering can stay unchanged. */
  const subclassOfFrontierForHierarchy = useMemo(() => {
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
          n.type.toLowerCase().includes(q),
      );
    }
    if (activeBuckets.size > 0) {
      nodes = nodes.filter((n) => activeBuckets.has(resolveNodeBucket(n, baseMap)));
    }
    return nodes;
  }, [graphSearchQuery, activeBuckets, graphNodes]);

  const subclassOfFrontierIris = useMemo(
    () => subclassOfFrontierForHierarchy.map((n) => n.id),
    [subclassOfFrontierForHierarchy],
  );
  const subclassOfFrontierKey = useMemo(
    () => [...subclassOfFrontierIris].sort().join(','),
    [subclassOfFrontierIris],
  );

  const hierarchyQuery = useOntologyHierarchy({
    ontologyPath,
    classIris: subclassOfFrontierIris,
    enabled: subclassOfEnabled && Boolean(ontologyPath),
  });
  const loadingSubclassOfHierarchy = hierarchyQuery.isFetching;

  const hierarchyByLevel = useMemo<
    Array<{
      level: number;
      nodes: OntologyOverviewGraphNode[];
      edges: OntologyOverviewGraphEdge[];
    }>
  >(() => {
    if (!hierarchyQuery.data) return [];
    const rawNodes = hierarchyQuery.data.nodes;
    const rawEdges = hierarchyQuery.data.edges;
    if (rawNodes.length === 0) return [];

    const nodesByLevel = new Map<number, OntologyOverviewGraphNode[]>();
    const levelById = new Map<string, number>();
    let maxLevel = 0;
    for (const raw of rawNodes) {
      const lvl =
        typeof raw.properties?.level === 'number' ? (raw.properties.level as number) : 1;
      if (lvl > maxLevel) maxLevel = lvl;
      const node: OntologyOverviewGraphNode = {
        id: raw.id,
        label: raw.label,
        type: raw.type,
        properties: raw.properties ?? {},
      };
      const arr = nodesByLevel.get(lvl) ?? [];
      arr.push(node);
      nodesByLevel.set(lvl, arr);
      levelById.set(node.id, lvl);
    }
    for (const arr of nodesByLevel.values()) {
      arr.sort((a, b) => a.label.localeCompare(b.label));
    }

    const edgesByLevel = new Map<number, OntologyOverviewGraphEdge[]>();
    for (const e of rawEdges) {
      if (e.properties?.relation_kind !== 'is_a') continue;
      const srcLvl = levelById.get(e.source);
      if (srcLvl === undefined) continue;
      const arr = edgesByLevel.get(srcLvl) ?? [];
      arr.push({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        label: e.label,
        properties: e.properties,
      });
      edgesByLevel.set(srcLvl, arr);
    }

    const out: Array<{
      level: number;
      nodes: OntologyOverviewGraphNode[];
      edges: OntologyOverviewGraphEdge[];
    }> = [];
    for (let lvl = 1; lvl <= maxLevel; lvl++) {
      out.push({
        level: lvl,
        nodes: nodesByLevel.get(lvl) ?? [],
        edges: edgesByLevel.get(lvl) ?? [],
      });
    }
    return out;
  }, [hierarchyQuery.data]);

  // Reset the hidden-top-levels filter whenever the frontier changes — the
  // hierarchy itself refetches automatically through the query key.
  useEffect(() => {
    setSubclassOfHiddenTopLevels(0);
  }, [subclassOfFrontierKey]);

  // Auto-enable SubclassOf the first time the graph finishes loading for an
  // ontology. Resets per ontology so switching ontologies re-applies it.
  const autoExpandedForPathRef = useRef<string | null>(null);
  const wasLoadingRef = useRef(false);
  useEffect(() => {
    if (autoExpandedForPathRef.current === ontologyPath) return;
    if (loadingGraph) {
      wasLoadingRef.current = true;
      return;
    }
    if (!wasLoadingRef.current) return;
    wasLoadingRef.current = false;
    if (!ontologyPath || graphNodes.length === 0) return;
    autoExpandedForPathRef.current = ontologyPath;
    setSubclassOfEnabled(true);
  }, [ontologyPath, loadingGraph, graphNodes.length]);

  const handleSubclassOfToggle = useCallback(() => {
    if (!ontologyPath) return;
    if (subclassOfEnabled) {
      setSubclassOfEnabled(false);
    } else {
      setSubclassOfEnabled(true);
      void hierarchyQuery.refetch();
    }
  }, [ontologyPath, subclassOfEnabled, hierarchyQuery]);

  const totalSubclassOfLevels = useMemo(
    () => hierarchyByLevel.length,
    [hierarchyByLevel.length],
  );
  const visibleSubclassOfMinLevel = useMemo(
    () => 1 + Math.min(subclassOfHiddenTopLevels, Math.max(0, totalSubclassOfLevels - 1)),
    [subclassOfHiddenTopLevels, totalSubclassOfLevels],
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
          node.type.toLowerCase().includes(query),
      );
    }

    if (activeBuckets.size > 0) {
      nodes = nodes.filter((node) => activeBuckets.has(resolveNodeBucket(node, nodesByIri)));
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
  }, [
    nodesMatchingSearchAndBuckets,
    focusedNodeId,
    showRestrictions,
    showObjectProperties,
    subclassOfEnabled,
    visibleHierarchyLevels,
    graphEdges,
    nodesByIri,
  ]);

  const nodesAfterLevelFilter = useMemo(() => {
    if (!subclassOfEnabled) return expandedNodes;
    return expandedNodes.filter((n) => {
      const lvl = nodeLevelById.get(n.id);
      // Missing level info → keep visible (avoids accidental hides during partial loads).
      if (lvl === undefined) return true;
      return lvl >= visibleSubclassOfMinLevel;
    });
  }, [expandedNodes, nodeLevelById, subclassOfEnabled, visibleSubclassOfMinLevel]);

  // User-selected + auto-activated buckets for relation-expanded nodes.
  const effectiveActiveBuckets = useMemo(() => {
    if (activeBuckets.size === 0) return activeBuckets;
    const result = new Set(activeBuckets);
    for (const node of nodesAfterLevelFilter) {
      result.add(resolveNodeBucket(node, nodesByIri));
    }
    return result;
  }, [activeBuckets, nodesAfterLevelFilter, nodesByIri]);

  const nodesPerBucketForPanel = useMemo(() => {
    const map = new Map<string, Array<{ id: string; label: string }>>();
    for (const node of nodesAfterLevelFilter) {
      const bucket = resolveNodeBucket(node, nodesByIri);
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

  // When subclassOf is ON and a node is focused, advance the level slider to the
  // focused node's level so only that node and its descendants are visible.
  // Unfocusing resets the slider back to 0 (show all levels).
  useEffect(() => {
    if (!subclassOfEnabled) return;
    if (!focusedNodeId) {
      setSubclassOfHiddenTopLevels(0);
      return;
    }
    const level = nodeLevelById.get(focusedNodeId);
    if (level === undefined) return;
    setSubclassOfHiddenTopLevels(level - 1);
  }, [focusedNodeId, subclassOfEnabled, nodeLevelById]);

  const filteredGraphEdges = useMemo(() => {
    const importEdges = graphEdges.filter((e) => e.properties?.relation_kind === 'imports');
    const restrictionEdges = graphEdges.filter(
      (e) => e.properties?.relation_kind === 'restriction',
    );
    const objectPropEdges = graphEdges.filter(
      (e) => e.properties?.relation_kind === 'object_property',
    );

    let baseEdges: OntologyOverviewGraphEdge[] = [...importEdges];

    if (subclassOfEnabled) {
      for (const level of visibleHierarchyLevels) {
        baseEdges = [...baseEdges, ...level.edges];
      }
    }

    if (showRestrictions) baseEdges = [...baseEdges, ...restrictionEdges];
    if (showObjectProperties) baseEdges = [...baseEdges, ...objectPropEdges];

    const needsNodeMask =
      Boolean(graphSearchQuery.trim()) ||
      activeBuckets.size > 0 ||
      Boolean(focusedNodeId) ||
      hiddenNodeIds.size > 0 ||
      showRestrictions ||
      showObjectProperties;
    if (!needsNodeMask) return baseEdges;
    const visibleNodeIds = new Set(filteredGraphNodes.map((node) => node.id));
    return baseEdges.filter(
      (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target),
    );
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

  const graphNodesById = useMemo(
    () => new Map(allVisibleNodes.map((node) => [node.id, node])),
    [allVisibleNodes],
  );
  const selectedGraphNode = selectedGraphNodeId
    ? graphNodesById.get(selectedGraphNodeId)
    : null;
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
                    onClick={handleSubclassOfToggle}
                    title={
                      subclassOfEnabled
                        ? 'Hide SubclassOf hierarchy'
                        : 'Show full SubclassOf hierarchy (rdfs:subClassOf)'
                    }
                    disabled={loadingSubclassOfHierarchy}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-1.5 text-xs',
                      subclassOfEnabled
                        ? 'bg-foreground text-background'
                        : 'text-muted-foreground hover:text-foreground',
                      loadingSubclassOfHierarchy && 'opacity-60 cursor-not-allowed',
                    )}
                  >
                    {loadingSubclassOfHierarchy ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <GitBranch size={12} />
                    )}
                    SubclassOf
                    {subclassOfEnabled &&
                      totalSubclassOfLevels > 0 &&
                      ` (${totalSubclassOfLevels - subclassOfHiddenTopLevels})`}
                  </button>
                  {subclassOfEnabled && totalSubclassOfLevels > 1 && (
                    <button
                      onClick={() =>
                        setSubclassOfHiddenTopLevels((v) =>
                          Math.min(totalSubclassOfLevels - 1, v + 1),
                        )
                      }
                      title="Hide top level (−1)"
                      disabled={
                        loadingSubclassOfHierarchy ||
                        subclassOfHiddenTopLevels >= totalSubclassOfLevels - 1
                      }
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
                  </div>
                )}
                <button
                  onClick={() => setShowRestrictions((v) => !v)}
                  title="Toggle OWL Restrictions (owl:Restriction)"
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs shadow-sm',
                    showRestrictions
                      ? 'border-foreground bg-foreground text-background'
                      : 'border-border bg-card text-muted-foreground hover:text-foreground',
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
                      : 'border-border bg-card text-muted-foreground hover:text-foreground',
                  )}
                >
                  <ArrowRight size={12} />
                  Object Properties
                </button>
              </>
            )}
            {(graphSearchQuery.trim() ||
              activeBuckets.size > 0 ||
              focusedNodeId ||
              hiddenNodeIds.size > 0) && (
              <span className="flex items-center rounded-lg border bg-card/80 px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
                Showing {filteredGraphNodes.length} of {expandedNodes.length}{' '}
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
              {isAllOntologiesOverview
                ? 'No ontologies found for this selection.'
                : 'No classes found for this ontology.'}
            </div>
          ) : (
            <VisNetwork
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
              stabilizeKey={graphStabilizeKey}
              layoutDirection={subclassOfEnabled ? layoutDirection : undefined}
              viewStateKey={ontologyGraphViewStateKey}
              physicsEnabled={physicsEnabled}
              centerOnNodeId={focusedNodeId}
            />
          )}
        </div>

        {(selectedGraphNode || selectedGraphEdge) && (
          <div className="w-80 flex-shrink-0 border-l bg-card">
            <div className="flex h-10 items-center justify-between border-b px-4">
              <span className="text-sm font-medium">Inspector</span>
              <button
                onClick={handleUnfocus}
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
                    <p>
                      {String(
                        selectedGraphNodeIsOntology
                          ? selectedGraphNodeDescription
                          : selectedGraphNode.properties?.definition || 'No definition',
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {isAllOntologiesOverview ? 'Version Info' : 'Subclass Of'}
                    </p>
                    <p>
                      {String(
                        isAllOntologiesOverview
                          ? selectedGraphNode.properties?.version_info || 'N/A'
                          : selectedGraphNode.properties?.parent_label ||
                            selectedGraphNode.properties?.parent_iri ||
                            'None',
                      )}
                    </p>
                  </div>
                  {isAllOntologiesOverview && (
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Source Path
                      </p>
                      <p className="break-all font-mono text-xs">
                        {String(selectedGraphNode.properties?.source_path || 'N/A')}
                      </p>
                    </div>
                  )}
                  {!isAllOntologiesOverview && (
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        BFO Bucket
                      </p>
                      <p>{resolveNodeBucket(selectedGraphNode, nodesByIri)}</p>
                    </div>
                  )}
                  {!isAllOntologiesOverview && selectedGraphNodeLevel !== null && (
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Level
                      </p>
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
                        handleUnfocus();
                        return;
                      }
                      setFocusedNodeId(selectedGraphNode.id);
                    }}
                    className={cn(
                      'flex w-full items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                      focusedNodeId === selectedGraphNode.id
                        ? 'border-workspace-accent bg-workspace-accent-10 text-workspace-accent'
                        : 'border-border bg-muted/40 hover:bg-muted',
                      !nodesMatchingSearchAndBuckets.some(
                        (n) => n.id === selectedGraphNode.id,
                      ) && 'cursor-not-allowed opacity-50',
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
                    <span className="font-medium">
                      {selectedGraphEdge.label || selectedGraphEdge.type}
                    </span>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Type</p>
                    <p>{isAllOntologiesOverview ? 'Dependency' : 'Relation'}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Kind</p>
                    <p>
                      {String(
                        selectedGraphEdge.properties?.relation_kind ||
                          (isAllOntologiesOverview ? 'imports' : 'object_property'),
                      )}
                    </p>
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
                    <p>
                      {graphNodesById.get(selectedGraphEdge.source)?.label ||
                        selectedGraphEdge.source}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {isAllOntologiesOverview ? 'Imported Ontology' : 'To'}
                    </p>
                    <p>
                      {graphNodesById.get(selectedGraphEdge.target)?.label ||
                        selectedGraphEdge.target}
                    </p>
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
