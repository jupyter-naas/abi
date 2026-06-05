'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  Check,
  ChevronDown,
  Download,
  GitBranch,
  Loader2,
  Network,
  RefreshCw,
  Search,
  Tag,
  Users,
  X,
} from 'lucide-react';
import { KpiCard } from '@/app/analytics/components/kpi-card';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import {
  useKnowledgeGraphStore,
  type GraphEdge as StoreGraphEdge,
  type GraphNode as StoreGraphNode,
} from '@/stores/knowledge-graph';
import { BFO_BUCKET_BY_URI } from '@/lib/bfo-buckets';
import {
  GraphNodeTable,
  type ApiNodeInstance,
  type ApiRelationTableRow,
} from '@/components/graph/graph-node-table';

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

interface ApiGraphKpis {
  individuals: number;
  relations: number;
  properties: number;
}

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
  object_properties?: Record<string, { uri: string; label: string }>;
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

// ─── PropertyPickerButton ─────────────────────────────────────────────────────

function PropertyPickerButton({
  classLabel,
  available,
  selected,
  onChange,
}: {
  classLabel: string;
  available: { uri: string; label: string }[];
  selected: string[];
  onChange: (newUris: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

  useEffect(() => {
    if (!open) return;
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setPos({ top: rect.bottom + window.scrollY + 2, left: rect.left + window.scrollX });
    }
    function handle(e: MouseEvent) {
      if (
        dropRef.current && !dropRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) setOpen(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [open]);

  function toggleProp(uri: string) {
    if (uri === RDFS_LABEL) return; // cannot uncheck label
    const next = selected.includes(uri)
      ? selected.filter((u) => u !== uri)
      : [...selected, uri];
    onChange(next);
  }

  return (
    <div className="relative">
      <button
        ref={btnRef}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex items-center gap-1 rounded border border-border px-2 py-0.5 text-xs hover:bg-muted transition-colors',
          open && 'bg-muted',
        )}
        title={`Select properties for ${classLabel}`}
      >
        <Tag size={10} />
        <span>{classLabel}</span>
        <ChevronDown size={10} className={cn('transition-transform', open && 'rotate-180')} />
      </button>

      {open && pos && typeof document !== 'undefined' && (
        <div
          ref={dropRef}
          style={{ position: 'fixed', top: pos.top, left: pos.left, zIndex: 9999 }}
          className="w-56 rounded border border-border bg-popover shadow-xl flex flex-col max-h-64 text-xs"
        >
          <div className="border-b border-border px-2 py-1.5 font-semibold text-muted-foreground shrink-0">
            {classLabel} properties
          </div>
          <div className="overflow-y-auto">
            {available.length === 0 ? (
              <p className="px-2 py-3 text-center text-muted-foreground">No properties available</p>
            ) : (
              available.map((prop) => {
                const isLabel = prop.uri === RDFS_LABEL;
                const isSelected = selected.includes(prop.uri);
                return (
                  <label
                    key={prop.uri}
                    className={cn(
                      'flex cursor-pointer items-center gap-2 px-2 py-1 hover:bg-muted/40',
                      isLabel && 'opacity-60 cursor-default',
                    )}
                    title={prop.uri}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={isLabel}
                      onChange={() => toggleProp(prop.uri)}
                      className="h-3.5 w-3.5 cursor-pointer accent-workspace-accent disabled:cursor-default"
                    />
                    <span className="truncate flex-1">{prop.label || prop.uri.split(/[#/]/).pop()}</span>
                    {isLabel && <span className="text-[10px] text-muted-foreground ml-auto">default</span>}
                  </label>
                );
              })
            )}
          </div>
          <div className="border-t border-border px-2 py-1 shrink-0 flex justify-end">
            <button
              onClick={() => setOpen(false)}
              className="flex items-center gap-1 rounded bg-workspace-accent px-2 py-0.5 text-[10px] font-medium text-white hover:opacity-80"
            >
              <Check size={10} />
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── NetworkPane ──────────────────────────────────────────────────────────────

function NetworkPane({
  workspaceId,
  activeGraph,
  kpis,
}: {
  workspaceId: string;
  activeGraph: ApiGraphInfo;
  kpis: ApiGraphKpis | null;
}) {
  const [loading, setLoading] = useState(true);
  const [nodes, setNodes] = useState<StoreGraphNode[]>([]);
  const [edges, setEdges] = useState<StoreGraphEdge[]>([]);
  const [stabilizeKey] = useState(0);
  const [activeBuckets, setActiveBuckets] = useState<Set<string>>(new Set());
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());

  // ── Table state ──
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>([]);
  const [availableProps, setAvailableProps] = useState<Record<string, { uri: string; label: string }[]>>({});
  const [selectedPropUris, setSelectedPropUris] = useState<Record<string, string[]>>({});
  const [nodeInstances, setNodeInstances] = useState<Record<string, ApiNodeInstance[]>>({});
  const [tableLoading, setTableLoading] = useState(false);
  const [relationTableRows, setRelationTableRows] = useState<ApiRelationTableRow[]>([]);

  const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

  // Load graph network
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
        const seenTriples = new Set<string>();
        for (const rel of relData) {
          const tripleKey = `${rel.domain_uri}|${rel.relation_uri}|${rel.range_uri}`;
          if (seenTriples.has(tripleKey)) continue;
          seenTriples.add(tripleKey);
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
        // Reset table state when graph changes
        setSelectedClassIds([]);
        setNodeInstances({});
        setAvailableProps({});
        setSelectedPropUris({});
        setRelationTableRows([]);
      } catch {
        // ignore errors silently — empty graph shown
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [workspaceId, activeGraph.uri]);

  // ── Graph node selection ──────────────────────────────────────────────────

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

  // ── Node selection for table ─────────────────────────────────────────────

  const filteredEdgesRef = useRef(filteredEdges);
  filteredEdgesRef.current = filteredEdges;

  const handleNodeSelect = useCallback((nodeId: string | null) => {
    if (!nodeId) {
      setSelectedClassIds([]);
      return;
    }
    setSelectedClassIds((prev) => {
      if (prev.includes(nodeId)) {
        return prev.filter((id) => id !== nodeId);
      }
      if (prev.length === 0) {
        return [nodeId];
      }
      if (prev.length === 1) {
        const edges = filteredEdgesRef.current;
        const hasEdge = edges.some(
          (e) =>
            (e.source === prev[0] && e.target === nodeId) ||
            (e.source === nodeId && e.target === prev[0])
        );
        if (!hasEdge) {
          return [nodeId];
        }
        return [prev[0], nodeId];
      }
      return [nodeId];
    });
  }, []);

  // ── displayNodes: mark selected nodes ────────────────────────────────────

  const displayNodes = useMemo(
    () =>
      filteredNodes.map((n) => ({
        ...n,
        properties: {
          ...n.properties,
          selected: selectedClassIds.includes(n.id),
        },
      })),
    [filteredNodes, selectedClassIds]
  );

  const tableOpen = selectedClassIds.length > 0;

  // ── Get class label from nodeId ───────────────────────────────────────────

  const getClassLabel = useCallback(
    (classId: string) => {
      const node = nodes.find((n) => n.id === classId);
      return node?.type ?? compactUri(classId);
    },
    [nodes]
  );

  // ── Fetch instances + properties when selectedClassIds changes ────────────

  useEffect(() => {
    if (selectedClassIds.length === 0) {
      setNodeInstances({});
      setRelationTableRows([]);
      return;
    }

    let cancelled = false;

    (async () => {
      setTableLoading(true);
      try {
        const newInstances: Record<string, ApiNodeInstance[]> = {};

        for (const classId of selectedClassIds) {
          // Fetch available properties if not already loaded
          let propsForClass = availableProps[classId];
          if (!propsForClass) {
            const propRes = await authFetch(
              `${getApiUrl()}/api/graph/network/node-properties`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  workspace_id: workspaceId,
                  graph_uri: activeGraph.uri,
                  class_uri: classId,
                }),
              }
            );
            if (!propRes.ok || cancelled) continue;
            const propData = (await propRes.json()) as { uri: string; label: string; kind: string }[];
            if (cancelled) return;
            propsForClass = propData;
            setAvailableProps((prev) => ({ ...prev, [classId]: propData }));
            if (!selectedPropUris[classId]) {
              setSelectedPropUris((prev) => ({
                ...prev,
                [classId]: [RDFS_LABEL],
              }));
            }
          }

          // Fetch instances
          const propUris = selectedPropUris[classId] ?? [RDFS_LABEL];
          const instRes = await authFetch(
            `${getApiUrl()}/api/graph/network/node-instances`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                workspace_id: workspaceId,
                graph_uri: activeGraph.uri,
                class_uri: classId,
                property_uris: propUris,
              }),
            }
          );
          if (!instRes.ok || cancelled) continue;
          const instData = (await instRes.json()) as ApiDiscoveryInstance[];
          if (cancelled) return;

          newInstances[classId] = instData.map((i) => ({
            uri: i.uri,
            label: i.label,
            properties: i.properties,
          }));
        }

        if (!cancelled) {
          setNodeInstances((prev) => ({ ...prev, ...newInstances }));
        }
      } finally {
        if (!cancelled) setTableLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClassIds, workspaceId, activeGraph?.uri]);

  // ── Fetch relation rows when both classes have instances ──────────────────

  useEffect(() => {
    if (selectedClassIds.length !== 2) {
      setRelationTableRows([]);
      return;
    }
    const [classA, classB] = selectedClassIds;
    const instancesA = nodeInstances[classA];
    const instancesB = nodeInstances[classB];
    if (!instancesA || !instancesB) return;

    let cancelled = false;
    (async () => {
      const allUris = [
        ...instancesA.map((i) => i.uri),
        ...instancesB.map((i) => i.uri),
      ];
      if (allUris.length === 0) return;

      const res = await authFetch(
        `${getApiUrl()}/api/graph/discovery/relations`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            instance_uris: allUris,
            relation_uris: [],
          }),
        }
      );
      if (!res.ok || cancelled) return;
      const relData = (await res.json()) as ApiDiscoveryRelationRow[];

      const propMapA = new Map(instancesA.map((i) => [i.uri, i.properties]));
      const propMapB = new Map(instancesB.map((i) => [i.uri, i.properties]));
      const uriSetA = new Set(instancesA.map((i) => i.uri));
      const uriSetB = new Set(instancesB.map((i) => i.uri));

      const rows: ApiRelationTableRow[] = [];
      const seen = new Set<string>();
      for (const r of relData) {
        const isDomainAtoB = uriSetA.has(r.domain_uri) && uriSetB.has(r.range_uri);
        const isDomainBtoA = uriSetB.has(r.domain_uri) && uriSetA.has(r.range_uri);
        if (!isDomainAtoB && !isDomainBtoA) continue;

        const key = `${r.domain_uri}|${r.relation_uri}|${r.range_uri}`;
        if (seen.has(key)) continue;
        seen.add(key);

        const domainProps = isDomainAtoB
          ? (propMapA.get(r.domain_uri) ?? {})
          : (propMapB.get(r.domain_uri) ?? {});
        const rangeProps = isDomainAtoB
          ? (propMapB.get(r.range_uri) ?? {})
          : (propMapA.get(r.range_uri) ?? {});

        rows.push({
          relation_label: r.relation_label,
          domain_uri: r.domain_uri,
          domain_label: r.domain_label,
          domain_properties: domainProps,
          range_uri: r.range_uri,
          range_label: r.range_label,
          range_properties: rangeProps,
        });
      }

      if (!cancelled) setRelationTableRows(rows);
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedClassIds, nodeInstances, workspaceId, activeGraph?.uri]);

  // ── Property change handler ───────────────────────────────────────────────

  const handlePropChange = useCallback(
    async (classId: string, newPropUris: string[]) => {
      setSelectedPropUris((prev) => ({ ...prev, [classId]: newPropUris }));
      setTableLoading(true);
      try {
        const instRes = await authFetch(
          `${getApiUrl()}/api/graph/network/node-instances`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              workspace_id: workspaceId,
              graph_uri: activeGraph.uri,
              class_uri: classId,
              property_uris: newPropUris,
            }),
          }
        );
        if (!instRes.ok) return;
        const instData = (await instRes.json()) as ApiDiscoveryInstance[];
        setNodeInstances((prev) => ({
          ...prev,
          [classId]: instData.map((i) => ({
            uri: i.uri,
            label: i.label,
            properties: i.properties,
          })),
        }));
      } finally {
        setTableLoading(false);
      }
    },
    [workspaceId, activeGraph]
  );

  // ── Derived data for the table ────────────────────────────────────────────

  const isDualMode = selectedClassIds.length === 2;
  const [classA, classB] = selectedClassIds;

  // Extra props (excluding RDFS_LABEL which maps to the .label column)
  const extraPropsA = (selectedPropUris[classA] ?? [RDFS_LABEL]).filter(
    (u) => u !== RDFS_LABEL
  );
  const extraPropsB = isDualMode
    ? (selectedPropUris[classB] ?? [RDFS_LABEL]).filter((u) => u !== RDFS_LABEL)
    : [];

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 size={20} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Graph area */}
      <div
        className="relative overflow-hidden"
        style={{ flex: tableOpen ? '0 0 60%' : '1 1 auto' }}
      >
        <VisNetwork
          nodes={displayNodes}
          edges={filteredEdges}
          selectedNodeId={null}
          onNodeSelect={handleNodeSelect}
          onEdgeSelect={() => {}}
          physicsEnabled={true}
          stabilizeKey={stabilizeKey}
          fillContainer={true}
        />
        {/* KPI cards overlay */}
        <div className="absolute left-3 top-3 z-10 grid grid-cols-4 gap-3 w-[calc(100%-theme(spacing.6))] pointer-events-none">
          {kpis ? (
            <>
              <KpiCard label="Individuals" value={kpis.individuals.toLocaleString()} hint="Unique OWL NamedIndividuals in this graph" icon={Users} className="pointer-events-auto" />
              <KpiCard label="Relations" value={kpis.relations.toLocaleString()} hint="Object property links between individuals" icon={GitBranch} className="pointer-events-auto" />
              <KpiCard label="Properties" value={kpis.properties.toLocaleString()} hint="Literal data values attached to individuals" icon={Tag} className="pointer-events-auto" />
            </>
          ) : (
            <>
              <div className="border border-border/60 bg-card animate-pulse h-[110px]" />
              <div className="border border-border/60 bg-card animate-pulse h-[110px]" />
              <div className="border border-border/60 bg-card animate-pulse h-[110px]" />
            </>
          )}
        </div>
        <BFOBucketFilters
          activeBuckets={activeBuckets}
          onToggle={handleBucketToggle}
          nodesPerBucket={nodesPerBucket}
          hiddenNodeIds={hiddenNodeIds}
          onNodeToggle={handleNodeToggle}
        />
      </div>

      {/* Table section */}
      {tableOpen && (
        <div
          className="flex flex-col border-t overflow-hidden"
          style={{ flex: '0 0 40%' }}
        >
          {/* Table header */}
          <div className="flex items-center gap-3 border-b px-4 py-2 bg-muted/30 text-sm shrink-0">
            <span className="font-semibold">
              {isDualMode
                ? `${getClassLabel(classA)} × ${getClassLabel(classB)}`
                : getClassLabel(classA)}
            </span>

            {/* Property pickers */}
            {selectedClassIds.map((classId) => (
              <PropertyPickerButton
                key={classId}
                classLabel={getClassLabel(classId)}
                available={availableProps[classId] ?? []}
                selected={selectedPropUris[classId] ?? [RDFS_LABEL]}
                onChange={(newUris) => void handlePropChange(classId, newUris)}
              />
            ))}

            {tableLoading && (
              <Loader2 size={12} className="animate-spin text-muted-foreground" />
            )}

            {/* Close button */}
            <button
              onClick={() => setSelectedClassIds([])}
              className="ml-auto rounded p-0.5 hover:bg-muted transition-colors"
              title="Close table"
            >
              <X size={14} />
            </button>
          </div>

          {/* Table content */}
          <div className="flex-1 overflow-auto px-4 py-3">
            {tableLoading && Object.keys(nodeInstances).length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : isDualMode ? (
              <GraphNodeTable
                mode="dual"
                domainClassLabel={getClassLabel(classA)}
                rangeClassLabel={getClassLabel(classB)}
                relationRows={relationTableRows}
                domainSelectedPropUris={extraPropsA}
                rangeSelectedPropUris={extraPropsB}
              />
            ) : (
              <GraphNodeTable
                mode="single"
                classLabel={getClassLabel(classA)}
                instances={nodeInstances[classA] ?? []}
                domainSelectedPropUris={extraPropsA}
              />
            )}
          </div>
        </div>
      )}
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
  const [kpis, setKpis] = useState<ApiGraphKpis | null>(null);

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

  useEffect(() => {
    if (!activeGraph) { setKpis(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch(
          `${getApiUrl()}/api/graph/kpis?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}`
        );
        if (!res.ok) return;
        const data = (await res.json()) as ApiGraphKpis;
        if (!cancelled) setKpis(data);
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [workspaceId, activeGraph]);

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
              <NetworkPane workspaceId={workspaceId} activeGraph={activeGraph} kpis={kpis} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
