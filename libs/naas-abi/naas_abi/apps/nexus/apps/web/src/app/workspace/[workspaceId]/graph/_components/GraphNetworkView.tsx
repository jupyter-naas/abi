'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  ArrowRight,
  GitBranch,
  Loader2,
  Network,
  RefreshCw,
  Search,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchNetworkParents } from '@/lib/api/graph';
import { resolveGraphNodeBucket } from './resolveGraphNodeBucket';
import type { GraphEdge, GraphNode } from './types';

const VisNetwork = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.VisNetwork),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center">
        <span className="text-muted-foreground">Loading graph...</span>
      </div>
    ),
  },
);

const BFOBucketFilters = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.BFOBucketFilters),
  { ssr: false },
);

export interface GraphNetworkViewProps {
  /** All nodes for the current graph selection. */
  nodes: GraphNode[];
  /** All edges for the current graph selection. */
  edges: GraphEdge[];
  loading: boolean;
  error: string | null;
  /** Selected node id — controlled by the page so the inspector can render alongside. */
  selectedNodeId: string | null;
  onNodeSelect: (id: string | null) => void;
  onEdgeSelect: (id: string | null) => void;
  /** Used as part of the canvas remount key + by `handleExpandParents`. */
  selectedGraphId: string | null;
  visibleGraphIds: string[];
  /** Used as part of the canvas remount key. */
  activeSavedViewId: string | null;
  /** Forwarded to the parents-fetch endpoint. */
  workspaceId: string;
  /** Called from the empty / error state's retry button. */
  reloadGraph: () => void;
}

/**
 * Self-contained network canvas for the instance graph.
 *
 * Owns every UI knob that only affects the canvas: search, BFO buckets,
 * hidden nodes, parent-class hierarchy expansion, relations toggle, node
 * display limit, and the physics-restart key. The page keeps `selectedNodeId`
 * (shared with the table view + inspector) and forwards it through.
 */
export function GraphNetworkView({
  nodes,
  edges,
  loading,
  error,
  selectedNodeId,
  onNodeSelect,
  onEdgeSelect,
  selectedGraphId,
  visibleGraphIds,
  activeSavedViewId,
  workspaceId,
  reloadGraph,
}: GraphNetworkViewProps) {
  // ── Filter / display state ─────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [activeBuckets, setActiveBuckets] = useState<Set<string>>(new Set());
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());
  const [nodeDisplayLimit, setNodeDisplayLimit] = useState(200);
  const [showRelations, setShowRelations] = useState(true);

  // Bumped whenever a filter requires a physics re-spread.
  const [stabilizeKey, setStabilizeKey] = useState(0);

  // Parents hierarchy (rdf:type → rdfs:subClassOf chain).
  const [parentsLevels, setParentsLevels] = useState(0);
  const [loadingNextParentLevel, setLoadingNextParentLevel] = useState(false);
  const [hierarchyByLevel, setHierarchyByLevel] = useState<
    Array<{ nodes: GraphNode[]; edges: GraphEdge[] }>
  >([]);

  // Reset filters when the active graph identity changes. Mirrors the previous
  // page-level reset effect to keep behaviour identical.
  useEffect(() => {
    setParentsLevels(0);
    setHierarchyByLevel([]);
    setShowRelations(true);
    setHiddenNodeIds(new Set());
    setNodeDisplayLimit(200);
  }, [selectedGraphId, activeSavedViewId]);

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
    setStabilizeKey((k) => k + 1);
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
      if (frontier.length === 0) {
        setParentsLevels(nextLevel);
        return;
      }

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
  }, [
    parentsLevels,
    hierarchyByLevel,
    loadingNextParentLevel,
    nodes,
    selectedGraphId,
    visibleGraphIds,
    workspaceId,
  ]);

  const canExpandParentsMore =
    parentsLevels < hierarchyByLevel.length ||
    (hierarchyByLevel[parentsLevels - 1]?.nodes.length ?? 1) > 0;

  // ── Derived data ──────────────────────────────────────────────────────────
  const allVisibleNodes = useMemo(() => {
    if (parentsLevels === 0) return nodes;
    const result = [...nodes];
    const seen = new Set(result.map((n) => n.id));
    for (let i = 0; i < parentsLevels && i < hierarchyByLevel.length; i++) {
      for (const node of hierarchyByLevel[i].nodes) {
        if (!seen.has(node.id)) {
          result.push(node);
          seen.add(node.id);
        }
      }
    }
    return result;
  }, [nodes, hierarchyByLevel, parentsLevels]);

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

  const filteredNodes = useMemo(() => {
    let result = allVisibleNodes;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (node) =>
          node.label.toLowerCase().includes(q) ||
          node.type.toLowerCase().includes(q) ||
          node.id.toLowerCase().includes(q),
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

  const filteredEdges = useMemo(() => {
    const visibleNodeIds = new Set(filteredNodes.map((n) => n.id));
    let result: GraphEdge[] = [];

    if (showRelations) {
      result = edges.filter(
        (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target),
      );
    }

    // is_a edges from loaded parent levels (always shown when their level is active).
    for (let i = 0; i < parentsLevels && i < hierarchyByLevel.length; i++) {
      for (const edge of hierarchyByLevel[i].edges) {
        if (visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)) {
          result.push(edge);
        }
      }
    }

    return result;
  }, [edges, filteredNodes, showRelations, parentsLevels, hierarchyByLevel]);

  const displayedNodes = useMemo(
    () => filteredNodes.slice(0, nodeDisplayLimit),
    [filteredNodes, nodeDisplayLimit],
  );

  const displayedEdges = useMemo(() => {
    const visibleIds = new Set(displayedNodes.map((n) => n.id));
    return filteredEdges.filter(
      (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
    );
  }, [filteredEdges, displayedNodes]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
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
          onClick={() => {
            setShowRelations((v) => !v);
            setStabilizeKey((k) => k + 1);
          }}
          title="Toggle relation edges (URIRef objects, excl. rdf:type)"
          className={cn(
            'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs shadow-sm',
            showRelations
              ? 'border-foreground bg-foreground text-background'
              : 'border-border bg-card text-muted-foreground hover:text-foreground',
          )}
        >
          <ArrowRight size={12} />
          Relations
        </button>
        {/* Parents filter — like SubclassOf in ontology page */}
        <div className="flex items-center rounded-lg border bg-card shadow-sm overflow-hidden">
          <button
            onClick={() =>
              parentsLevels === 0 ? handleExpandParents() : setParentsLevels(0)
            }
            title={
              parentsLevels === 0
                ? 'Show parent classes (rdf:type → rdfs:subClassOf)'
                : 'Hide parent hierarchy'
            }
            disabled={loadingNextParentLevel}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 text-xs',
              parentsLevels > 0
                ? 'bg-foreground text-background'
                : 'text-muted-foreground hover:text-foreground',
              loadingNextParentLevel && 'opacity-60 cursor-not-allowed',
            )}
          >
            {loadingNextParentLevel ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <GitBranch size={12} />
            )}
            Parents{parentsLevels > 0 && ` (${parentsLevels})`}
          </button>
          {parentsLevels > 0 && (
            <button
              onClick={() => setParentsLevels((v) => Math.max(0, v - 1))}
              title="Show fewer parent levels"
              disabled={loadingNextParentLevel}
              className="border-l px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60"
            >
              −
            </button>
          )}
          {canExpandParentsMore && (
            <button
              onClick={handleExpandParents}
              title="Show more parent levels"
              disabled={loadingNextParentLevel}
              className="border-l px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60"
            >
              +
            </button>
          )}
        </div>
        {(searchQuery ||
          filteredNodes.length < allVisibleNodes.length ||
          nodeDisplayLimit < filteredNodes.length) && (
          <span className="flex items-center rounded-lg border bg-card/80 px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
            Showing {Math.min(nodeDisplayLimit, filteredNodes.length)} of{' '}
            {allVisibleNodes.length} nodes
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
            onNodeSelect={onNodeSelect}
            onEdgeSelect={onEdgeSelect}
            stabilizeKey={stabilizeKey}
          />
          {filteredNodes.length > 0 && (
            <div className="absolute bottom-4 left-4 z-10 flex flex-col gap-1.5 rounded-lg border bg-card/95 px-3 py-2 shadow-lg backdrop-blur-sm w-52">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Nodes displayed</span>
                <span className="font-medium tabular-nums">
                  {Math.min(nodeDisplayLimit, filteredNodes.length)}
                  &nbsp;/&nbsp;{filteredNodes.length}
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
  );
}
