'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  ChevronDown,
  Download,
  Loader2,
  Network,
  RefreshCw,
  Search,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import {
  useKnowledgeGraphStore,
  type GraphEdge as StoreGraphEdge,
  type GraphNode as StoreGraphNode,
} from '@/stores/knowledge-graph';
import { BFO_BUCKET_BY_URI } from '@/lib/bfo-buckets';

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

const BFOBucketFilters = dynamic(
  () => import('@/components/graph/vis-network').then((mod) => mod.BFOBucketFilters),
  { ssr: false }
);

const DEFAULT_PROPERTY_URIS = ['http://www.w3.org/2000/01/rdf-schema#label'];

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

function resolveNodeBucketType(node: StoreGraphNode): string {
  const bfoParentIri = node.properties?.bfo_parent_iri as string | undefined;
  if (bfoParentIri) {
    const def = BFO_BUCKET_BY_URI[bfoParentIri];
    if (def) return def.type;
  }
  return 'Unknown';
}

function NetworkPane({
  workspaceId,
  activeGraph,
}: {
  workspaceId: string;
  activeGraph: ApiGraphInfo;
}) {
  const [loading, setLoading] = useState(true);
  const [nodes, setNodes] = useState<StoreGraphNode[]>([]);
  const [edges, setEdges] = useState<StoreGraphEdge[]>([]);
  const [stabilizeKey] = useState(0);
  const [activeBuckets, setActiveBuckets] = useState<Set<string>>(new Set());
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const classRes = await authFetch(
          `${getApiUrl()}/api/graph/discovery/classes?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}`
        );
        if (!classRes.ok) throw new Error(`status ${classRes.status}`);
        const classData = (await classRes.json()) as ApiDiscoveryClass[];
        const classUris = classData.map((c) => c.uri);

        const instRes = await authFetch(`${getApiUrl()}/api/graph/discovery/instances`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            class_uris: classUris,
            property_uris: DEFAULT_PROPERTY_URIS,
            search: '',
          }),
        });
        if (!instRes.ok) throw new Error(`status ${instRes.status}`);
        const instData = (await instRes.json()) as ApiDiscoveryInstance[];
        const instanceUris = instData.map((i) => i.uri);

        const relTypesRes = await authFetch(`${getApiUrl()}/api/graph/discovery/relation-types`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            instance_uris: instanceUris,
          }),
        });
        if (!relTypesRes.ok) throw new Error(`status ${relTypesRes.status}`);
        const relTypeData = (await relTypesRes.json()) as ApiDiscoveryRelationType[];
        const relationUris = relTypeData.map((r) => r.uri);

        let relData: ApiDiscoveryRelationRow[] = [];
        if (instanceUris.length > 0 && relationUris.length > 0) {
          const relRes = await authFetch(`${getApiUrl()}/api/graph/discovery/relations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              workspace_id: workspaceId,
              graph_uri: activeGraph.uri,
              instance_uris: instanceUris,
              relation_uris: relationUris,
            }),
          });
          if (!relRes.ok) throw new Error(`status ${relRes.status}`);
          relData = (await relRes.json()) as ApiDiscoveryRelationRow[];
        }

        if (cancelled) return;

        const classCounts = new Map<string, { label: string; count: number; bfoParentIri: string }>();
        for (const inst of instData) {
          const classUri = inst.class_uri || inst.class_label || '';
          if (!classUri) continue;
          const existing = classCounts.get(classUri);
          if (existing) { existing.count++; }
          else { classCounts.set(classUri, { label: inst.class_label || compactUri(inst.class_uri), count: 1, bfoParentIri: inst.bfo_bucket_uri || '' }); }
        }
        for (const rel of relData) {
          for (const [uri, label] of [
            [rel.domain_class_uri, rel.domain_class_label],
            [rel.range_class_uri, rel.range_class_label],
          ] as [string | undefined, string | undefined][]) {
            const classUri = uri || label || '';
            if (!classUri || classCounts.has(classUri)) continue;
            classCounts.set(classUri, { label: label || compactUri(uri || ''), count: 0, bfoParentIri: '' });
          }
        }
        const graphNodes: StoreGraphNode[] = Array.from(classCounts.entries()).map(
          ([classUri, { label, count, bfoParentIri }]) => ({
            id: classUri || label,
            label: count > 0 ? `${label} (${count})` : label,
            type: label,
            properties: { class_uri: classUri, bfo_parent_iri: bfoParentIri, selected: false },
          })
        );

        const edgeCounts = new Map<string, { domainClass: string; rangeClass: string; label: string; count: number }>();
        for (const rel of relData) {
          const domainClass = rel.domain_class_uri || rel.domain_class_label || '';
          const rangeClass = rel.range_class_uri || rel.range_class_label || '';
          if (!domainClass || !rangeClass) continue;
          const label = rel.relation_label || compactUri(rel.relation_uri);
          const key = `${domainClass}|${label}|${rangeClass}`;
          const existing = edgeCounts.get(key);
          if (existing) { existing.count++; }
          else { edgeCounts.set(key, { domainClass, rangeClass, label, count: 1 }); }
        }
        const graphEdges: StoreGraphEdge[] = Array.from(edgeCounts.entries()).map(
          ([key, { domainClass, rangeClass, label, count }]) => ({
            id: key,
            source: domainClass,
            target: rangeClass,
            type: label,
            label: `${label} (${count})`,
            properties: { selected: false },
          })
        );

        setNodes(graphNodes);
        setEdges(graphEdges);
        setActiveBuckets(new Set());
        setHiddenNodeIds(new Set());
      } catch {
        // ignore errors silently — empty graph shown
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [workspaceId, activeGraph.uri]);

  const handleBucketToggle = useCallback((bucketType: string) => {
    setActiveBuckets((prev) => {
      const next = new Set(prev);
      if (next.has(bucketType)) next.delete(bucketType);
      else next.add(bucketType);
      return next;
    });
  }, []);

  const handleNodeToggle = useCallback((nodeId: string) => {
    setHiddenNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const nodesPerBucket = useMemo(() => {
    const map = new Map<string, Array<{ id: string; label: string }>>();
    for (const node of nodes) {
      const bucket = resolveNodeBucketType(node);
      const existing = map.get(bucket) ?? [];
      existing.push({ id: node.id, label: node.label });
      map.set(bucket, existing);
    }
    return map;
  }, [nodes]);

  const visibleNodeIds = useMemo(() => {
    return new Set(
      nodes
        .filter((n) => {
          if (hiddenNodeIds.has(n.id)) return false;
          if (activeBuckets.size === 0) return true;
          return activeBuckets.has(resolveNodeBucketType(n));
        })
        .map((n) => n.id)
    );
  }, [nodes, activeBuckets, hiddenNodeIds]);

  const filteredNodes = useMemo(
    () => nodes.filter((n) => visibleNodeIds.has(n.id)),
    [nodes, visibleNodeIds]
  );

  const filteredEdges = useMemo(
    () => edges.filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)),
    [edges, visibleNodeIds]
  );

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 size={20} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="relative flex flex-1 overflow-hidden">
      <VisNetwork
        nodes={filteredNodes}
        edges={filteredEdges}
        selectedNodeId={null}
        onNodeSelect={() => {}}
        onEdgeSelect={() => {}}
        physicsEnabled={true}
        stabilizeKey={stabilizeKey}
        fillContainer={true}
      />
      <BFOBucketFilters
        activeBuckets={activeBuckets}
        onToggle={handleBucketToggle}
        nodesPerBucket={nodesPerBucket}
        hiddenNodeIds={hiddenNodeIds}
        onNodeToggle={handleNodeToggle}
      />
    </div>
  );
}

export default function NetworkPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;

  const {
    selectedGraphId,
    visibleGraphIds,
  } = useKnowledgeGraphStore();

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [graphsError, setGraphsError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<'ttl' | 'owl' | 'nt'>('ttl');
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

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

  const handleExport = useCallback(async () => {
    if (!activeGraph || exporting) return;
    setExporting(true);
    try {
      const url = `${getApiUrl()}/api/graph/export?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}&format=${exportFormat}`;
      const response = await authFetch(url);
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const blob = await response.blob();
      const filename = `${activeGraph.label || 'graph'}.${exportFormat}`;
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
  }, [activeGraph, exporting, workspaceId, exportFormat]);

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex h-10 items-center justify-between border-b bg-muted/30 px-4">
            <div className="flex items-center gap-1">
              <button
                onClick={() => router.push(`/workspace/${workspaceId}/graph/network`)}
                className={cn('flex items-center gap-2 rounded-md px-3 py-1 text-sm', 'bg-background')}
              >
                <Network size={14} />
                Network
              </button>
              <button
                onClick={() => router.push(`/workspace/${workspaceId}/graph/discovery`)}
                className="flex items-center gap-2 rounded-md px-3 py-1 text-sm text-muted-foreground hover:bg-background"
              >
                <Search size={14} />
                Discovery
              </button>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative flex items-center">
                <button
                  type="button"
                  onClick={() => void handleExport()}
                  disabled={!activeGraph || exporting}
                  className={cn(
                    'flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground',
                    (!activeGraph || exporting) && 'cursor-not-allowed opacity-50'
                  )}
                  title={!activeGraph ? 'Select a graph to export' : `Export graph as .${exportFormat}`}
                >
                  {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                  {exporting ? 'Exporting...' : 'Export'}
                </button>
                <button
                  type="button"
                  onClick={() => setExportMenuOpen((o) => !o)}
                  disabled={!activeGraph}
                  className={cn(
                    'ml-0.5 flex items-center rounded px-1 py-0.5 text-muted-foreground hover:text-foreground',
                    !activeGraph && 'cursor-not-allowed opacity-50'
                  )}
                  title="Select export format"
                >
                  <ChevronDown size={12} />
                </button>
                {exportMenuOpen && (
                  <div className="absolute right-0 top-full z-50 mt-1 min-w-[90px] rounded-md border bg-background shadow-md">
                    {(['ttl', 'owl', 'nt'] as const).map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        onClick={() => { setExportFormat(fmt); setExportMenuOpen(false); }}
                        className={cn(
                          'flex w-full items-center px-3 py-1.5 text-left text-sm hover:bg-muted',
                          exportFormat === fmt && 'font-medium text-foreground'
                        )}
                      >
                        .{fmt}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
          <div className="flex flex-1 overflow-hidden">
            {graphsLoading ? (
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
                <p className="text-sm text-muted-foreground">No graphs available in this workspace.</p>
              </div>
            ) : (
              <NetworkPane workspaceId={workspaceId} activeGraph={activeGraph} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
