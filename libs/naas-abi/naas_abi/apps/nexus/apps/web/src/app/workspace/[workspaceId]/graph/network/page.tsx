'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  Check,
  ChevronDown,
  GitBranch,
  Loader2,
  Network,
  RefreshCw,
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
import { GraphDevBanner } from '@/components/graph/graph-dev-banner';
import {
  GraphNodeTable,
  type ApiNodeInstance,
  type ApiRelationTableRow,
  type ChainTableRow,
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
  classes: number;
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

function pairKey(parentId: string, childId: string): string {
  return `${parentId}|${childId}`;
}

function edgesBetweenNodes(
  nodeA: string,
  nodeB: string,
  edgeList: StoreGraphEdge[],
): StoreGraphEdge[] {
  return edgeList.filter(
    (e) =>
      (e.source === nodeA && e.target === nodeB) ||
      (e.source === nodeB && e.target === nodeA),
  );
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
          <div className="border-t border-border px-2 py-1 shrink-0 flex justify-end gap-1.5">
            <button
              onClick={() => onChange([RDFS_LABEL])}
              className="flex items-center gap-1 rounded border border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X size={10} />
              Clear
            </button>
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

// ─── Chain helpers ────────────────────────────────────────────────────────────

function buildChainRows(
  selectedClassIds: string[],
  selectedPairs: Array<{ parentIdx: number; childIdx: number }>,
  nodeInstances: Record<string, ApiNodeInstance[]>,
  pairRelations: Record<string, ApiRelationTableRow[]>,
): ChainTableRow[] {
  if (selectedClassIds.length < 1) return [];

  type NormRow = {
    leftUri: string; leftLabel: string; leftProps: Record<string, string>;
    rel: string;
    rightUri: string; rightLabel: string; rightProps: Record<string, string>;
  };

  type Acc = { uris: string[]; labels: string[]; props: Record<string, string>[]; rels: string[] };

  // Seed from ALL instances of the first class — never drop them.
  const firstInst = nodeInstances[selectedClassIds[0]] ?? [];
  let accumulated: Acc[] = firstInst.map((x) => ({
    uris: [x.uri],
    labels: [x.label],
    props: [x.properties],
    rels: [],
  }));

  // Process each pair in selection order. parentIdx < childIdx is guaranteed,
  // so acc.uris[parentIdx] is always populated when we reach this pair.
  for (const pair of selectedPairs) {
    const { parentIdx, childIdx } = pair;
    const classA = selectedClassIds[parentIdx];
    const classB = selectedClassIds[childIdx];
    const instA = nodeInstances[classA] ?? [];
    const instB = nodeInstances[classB] ?? [];
    const mapA = new Map(instA.map((x) => [x.uri, { label: x.label, props: x.properties }]));
    const mapB = new Map(instB.map((x) => [x.uri, { label: x.label, props: x.properties }]));

    const relRows = pairRelations[`${classA}|${classB}`] ?? [];

    // Build bridge map keyed on classA URI (pre-normalized during fetch).
    const bridgeMap = new Map<string, NormRow[]>();
    for (const r of relRows) {
      const norm: NormRow = {
        leftUri: r.domain_uri,
        leftLabel: mapA.get(r.domain_uri)?.label ?? r.domain_label,
        leftProps: mapA.get(r.domain_uri)?.props ?? r.domain_properties,
        rel: r.relation_label,
        rightUri: r.range_uri,
        rightLabel: mapB.get(r.range_uri)?.label ?? r.range_label,
        rightProps: mapB.get(r.range_uri)?.props ?? r.range_properties,
      };
      const list = bridgeMap.get(norm.leftUri) ?? [];
      list.push(norm);
      bridgeMap.set(norm.leftUri, list);
    }

    // OUTER JOIN on the parent's URI (not necessarily the last accumulated URI).
    const next: Acc[] = [];
    const matchedRightUris = new Set<string>();
    for (const acc of accumulated) {
      const bridge = acc.uris[parentIdx];
      const matches = bridgeMap.get(bridge) ?? [];
      if (matches.length > 0) {
        for (const m of matches) {
          matchedRightUris.add(m.rightUri);
          next.push({
            uris: [...acc.uris, m.rightUri],
            labels: [...acc.labels, m.rightLabel],
            props: [...acc.props, m.rightProps],
            rels: [...acc.rels, m.rel],
          });
        }
      } else {
        next.push({
          uris: [...acc.uris, ''],
          labels: [...acc.labels, ''],
          props: [...acc.props, {}],
          rels: [...acc.rels, ''],
        });
      }
    }
    // Right-only rows: classB instances with no classA match
    for (const [uri, data] of mapB) {
      if (!matchedRightUris.has(uri)) {
        next.push({
          uris: [...Array(childIdx).fill(''), uri],
          labels: [...Array(childIdx).fill(''), data.label],
          props: [...Array(childIdx).fill({}), data.props],
          rels: Array(childIdx).fill('') as string[],
        });
      }
    }
    accumulated = next;
  }

  return accumulated.map((acc) => ({
    nodes: acc.uris.map((uri, i) => ({ uri, label: acc.labels[i], properties: acc.props[i] })),
    relations: acc.rels,
  }));
}

// ─── RelationPickerDialog ───────────────────────────────────────────────────

function RelationPickerDialog({
  parentId,
  childId,
  getClassLabel,
  edges,
  onPick,
  onCancel,
}: {
  parentId: string;
  childId: string;
  getClassLabel: (classId: string) => string;
  edges: StoreGraphEdge[];
  onPick: (edge: StoreGraphEdge) => void;
  onCancel: () => void;
}) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-background/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-border bg-popover p-4 shadow-xl">
        <h3 className="text-sm font-semibold">Choose a relation</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Multiple relations connect {getClassLabel(parentId)} and {getClassLabel(childId)}.
        </p>
        <ul className="mt-3 max-h-64 space-y-1 overflow-y-auto">
          {edges.map((edge) => (
            <li key={edge.id}>
              <button
                type="button"
                onClick={() => onPick(edge)}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-muted"
              >
                <GitBranch size={14} className="shrink-0 text-muted-foreground" />
                <span className="truncate">{getClassLabel(edge.source)}</span>
                <span className="shrink-0 text-muted-foreground">→</span>
                <span className="truncate font-medium">{edge.type}</span>
                <span className="shrink-0 text-muted-foreground">→</span>
                <span className="truncate">{getClassLabel(edge.target)}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── SelectionStats ───────────────────────────────────────────────────────────

function SelectionStats({ stats }: {
  stats: { rows: number; classes: number; individuals: number; relations: number; properties: number };
}) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <span><span className="font-medium text-foreground">{stats.rows.toLocaleString()}</span> Rows</span>
      <span>-</span>
      <span><span className="font-medium text-foreground">{stats.classes}</span> {stats.classes === 1 ? 'Class' : 'Classes'}</span>
      <span>-</span>
      <span><span className="font-medium text-foreground">{stats.individuals.toLocaleString()}</span> Individuals</span>
      <span>-</span>
      <span><span className="font-medium text-foreground">{stats.relations.toLocaleString()}</span> Relations</span>
      <span>-</span>
      <span><span className="font-medium text-foreground">{stats.properties.toLocaleString()}</span> Properties</span>
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
  const [pairRelations, setPairRelations] = useState<Record<string, ApiRelationTableRow[]>>({});
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([]);
  /** Maps ordered class pair (parent|child) to the chosen graph edge id. */
  const [selectedPairEdges, setSelectedPairEdges] = useState<Record<string, string>>({});
  const [relationPicker, setRelationPicker] = useState<{
    nodeId: string;
    parentId: string;
    edges: StoreGraphEdge[];
  } | null>(null);

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
        setPairRelations({});
        setSelectedEdgeIds([]);
        setSelectedPairEdges({});
        setRelationPicker(null);
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

  const clearSelection = useCallback(() => {
    setSelectedClassIds([]);
    setSelectedEdgeIds([]);
    setSelectedPairEdges({});
    setRelationPicker(null);
  }, []);

  const appendNodeWithEdge = useCallback(
    (prevClassIds: string[], parentId: string, nodeId: string, edge: StoreGraphEdge) => {
      setSelectedEdgeIds((prevEdges) => [...prevEdges, edge.id]);
      setSelectedPairEdges((prevPairs) => ({
        ...prevPairs,
        [pairKey(parentId, nodeId)]: edge.id,
      }));
      return [...prevClassIds, nodeId];
    },
    [],
  );

  const handleEdgeSelect = useCallback(
    (edgeId: string | null) => {
      if (!edgeId) {
        clearSelection();
        return;
      }
      const edge = filteredEdgesRef.current.find((e) => e.id === edgeId);
      if (!edge) return;

      setRelationPicker(null);
      setSelectedClassIds((prev) => {
        if (prev.length === 0) {
          setSelectedEdgeIds([edgeId]);
          setSelectedPairEdges({ [pairKey(edge.source, edge.target)]: edgeId });
          return [edge.source, edge.target];
        }

        // Update relation for an adjacent pair already in the chain.
        for (let i = 0; i < prev.length - 1; i++) {
          const a = prev[i];
          const b = prev[i + 1];
          const connects =
            (edge.source === a && edge.target === b) ||
            (edge.source === b && edge.target === a);
          if (!connects) continue;
          setSelectedEdgeIds((prevEdges) => {
            const next = [...prevEdges];
            next[i] = edgeId;
            return next.slice(0, prev.length - 1);
          });
          setSelectedPairEdges((prevPairs) => ({
            ...prevPairs,
            [pairKey(a, b)]: edgeId,
          }));
          return prev;
        }

        const lastId = prev[prev.length - 1];
        if (edge.source === lastId && !prev.includes(edge.target)) {
          setSelectedEdgeIds((prevEdges) => [...prevEdges, edgeId]);
          setSelectedPairEdges((prevPairs) => ({
            ...prevPairs,
            [pairKey(edge.source, edge.target)]: edgeId,
          }));
          return [...prev, edge.target];
        }
        if (edge.target === lastId && !prev.includes(edge.source)) {
          setSelectedEdgeIds((prevEdges) => [...prevEdges, edgeId]);
          setSelectedPairEdges((prevPairs) => ({
            ...prevPairs,
            [pairKey(edge.target, edge.source)]: edgeId,
          }));
          return [...prev, edge.source];
        }

        setSelectedEdgeIds([edgeId]);
        setSelectedPairEdges({ [pairKey(edge.source, edge.target)]: edgeId });
        return [edge.source, edge.target];
      });
    },
    [clearSelection],
  );

  const handleNodeSelect = useCallback(
    (nodeId: string | null) => {
      if (!nodeId) {
        clearSelection();
        return;
      }

      setSelectedClassIds((prev) => {
        if (prev.includes(nodeId)) {
          const idx = prev.indexOf(nodeId);
          const next = prev.slice(0, idx);
          setSelectedEdgeIds((prevEdges) => prevEdges.slice(0, Math.max(0, idx)));
          setSelectedPairEdges((prevPairs) => {
            const trimmed: Record<string, string> = {};
            for (let i = 0; i < next.length - 1; i++) {
              const key = pairKey(next[i], next[i + 1]);
              if (prevPairs[key]) trimmed[key] = prevPairs[key];
            }
            return trimmed;
          });
          setRelationPicker(null);
          return next;
        }

        if (prev.length === 0) {
          setSelectedEdgeIds([]);
          setSelectedPairEdges({});
          setRelationPicker(null);
          return [nodeId];
        }

        const edgeList = filteredEdgesRef.current;
        let parentId: string | null = null;
        for (let i = 0; i < prev.length; i++) {
          const candidate = prev[i];
          if (edgesBetweenNodes(candidate, nodeId, edgeList).length > 0) {
            parentId = candidate;
            break;
          }
        }

        if (!parentId) {
          setSelectedEdgeIds([]);
          setSelectedPairEdges({});
          setRelationPicker(null);
          return [nodeId];
        }

        const betweenEdges = edgesBetweenNodes(parentId, nodeId, edgeList);
        if (betweenEdges.length === 1) {
          setRelationPicker(null);
          return appendNodeWithEdge(prev, parentId, nodeId, betweenEdges[0]);
        }

        setRelationPicker({ nodeId, parentId, edges: betweenEdges });
        return prev;
      });
    },
    [appendNodeWithEdge, clearSelection],
  );

  const handleRelationPick = useCallback(
    (edge: StoreGraphEdge) => {
      if (!relationPicker) return;
      const { nodeId, parentId } = relationPicker;
      setRelationPicker(null);
      setSelectedClassIds((prev) => appendNodeWithEdge(prev, parentId, nodeId, edge));
    },
    [appendNodeWithEdge, relationPicker],
  );

  // ── Chain order and joined rows ───────────────────────────────────────────

  // Preserve click order: the first selected node is always leftmost in the table.
  const chainOrder = selectedClassIds;

  // For each node after the first, find its parent: the earliest-selected node
  // that has a direct edge to it. This handles star topologies (A→B, A→C)
  // as well as linear chains (A→B→C).
  const selectedPairs = useMemo(() => {
    const pairs: Array<{ parentIdx: number; childIdx: number }> = [];
    for (let childIdx = 1; childIdx < selectedClassIds.length; childIdx++) {
      for (let parentIdx = 0; parentIdx < childIdx; parentIdx++) {
        const childId = selectedClassIds[childIdx];
        const parentId = selectedClassIds[parentIdx];
        const hasEdge = filteredEdges.some(
          (e) =>
            (e.source === parentId && e.target === childId) ||
            (e.source === childId && e.target === parentId)
        );
        if (hasEdge) {
          pairs.push({ parentIdx, childIdx });
          break;
        }
      }
    }
    return pairs;
  }, [selectedClassIds, filteredEdges]);

  const filteredPairRelations = useMemo(() => {
    if (Object.keys(selectedPairEdges).length === 0) return pairRelations;
    const out: Record<string, ApiRelationTableRow[]> = { ...pairRelations };
    for (const pair of selectedPairs) {
      const classA = selectedClassIds[pair.parentIdx];
      const classB = selectedClassIds[pair.childIdx];
      const key = `${classA}|${classB}`;
      const rows = pairRelations[key];
      if (!rows) continue;
      const edgeId = selectedPairEdges[pairKey(classA, classB)];
      const edge = edgeId ? edges.find((e) => e.id === edgeId) : undefined;
      if (edge) {
        out[key] = rows.filter((r) => r.relation_label === edge.type);
      }
    }
    return out;
  }, [pairRelations, selectedPairEdges, selectedPairs, selectedClassIds, edges]);

  const chainTableRows = useMemo(
    () => buildChainRows(chainOrder, selectedPairs, nodeInstances, filteredPairRelations),
    [chainOrder, selectedPairs, nodeInstances, filteredPairRelations]
  );

  // ── When nodes are selected, restrict visible set to them + their neighbours

  const visibleBySelection = useMemo(() => {
    if (selectedClassIds.length === 0) return null; // null = show all
    const reachable = new Set<string>(selectedClassIds);
    for (const id of selectedClassIds) {
      for (const edge of filteredEdges) {
        if (edge.source === id) reachable.add(edge.target);
        if (edge.target === id) reachable.add(edge.source);
      }
    }
    return reachable;
  }, [selectedClassIds, filteredEdges]);

  const displayNodes = useMemo(
    () =>
      filteredNodes
        .filter((n) => visibleBySelection === null || visibleBySelection.has(n.id))
        .map((n) => ({
          ...n,
          properties: {
            ...n.properties,
            selected: selectedClassIds.includes(n.id),
          },
        })),
    [filteredNodes, selectedClassIds, visibleBySelection]
  );

  const displayEdges = useMemo(
    () => {
      const base =
        visibleBySelection === null
          ? filteredEdges
          : filteredEdges.filter(
              (e) => visibleBySelection.has(e.source) && visibleBySelection.has(e.target),
            );
      const hasEdgeSelection = selectedEdgeIds.length > 0;
      return base.map((e) => ({
        ...e,
        properties: {
          ...e.properties,
          selected: hasEdgeSelection ? selectedEdgeIds.includes(e.id) : false,
        },
      }));
    },
    [filteredEdges, visibleBySelection, selectedEdgeIds],
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
      setPairRelations({});
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

  // ── Fetch relation rows for each connected pair in the selection ──────────

  useEffect(() => {
    if (selectedClassIds.length < 2 || selectedPairs.length === 0) {
      setPairRelations({});
      return;
    }

    // Wait until all selected class instances are loaded.
    const allLoaded = selectedClassIds.every((id) => nodeInstances[id] !== undefined);
    if (!allLoaded) return;

    let cancelled = false;
    (async () => {
      const newPairRelations: Record<string, ApiRelationTableRow[]> = {};

      for (const pair of selectedPairs) {
        const classA = selectedClassIds[pair.parentIdx];
        const classB = selectedClassIds[pair.childIdx];
        const instancesA = nodeInstances[classA] ?? [];
        const instancesB = nodeInstances[classB] ?? [];

        const allUris = [
          ...instancesA.map((x) => x.uri),
          ...instancesB.map((x) => x.uri),
        ];
        if (allUris.length === 0) {
          newPairRelations[`${classA}|${classB}`] = [];
          continue;
        }

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
        if (!res.ok || cancelled) break;
        const relData = (await res.json()) as ApiDiscoveryRelationRow[];

        const uriSetA = new Set(instancesA.map((x) => x.uri));
        const uriSetB = new Set(instancesB.map((x) => x.uri));
        const propMapA = new Map(instancesA.map((x) => [x.uri, x.properties]));
        const propMapB = new Map(instancesB.map((x) => [x.uri, x.properties]));

        const rows: ApiRelationTableRow[] = [];
        const seen = new Set<string>();
        for (const r of relData) {
          const isAtoB = uriSetA.has(r.domain_uri) && uriSetB.has(r.range_uri);
          const isBtoA = uriSetB.has(r.domain_uri) && uriSetA.has(r.range_uri);
          if (!isAtoB && !isBtoA) continue;
          // Normalize: domain_uri = classA instance, range_uri = classB instance.
          const leftUri = isAtoB ? r.domain_uri : r.range_uri;
          const rightUri = isAtoB ? r.range_uri : r.domain_uri;
          const k = `${leftUri}|${r.relation_uri}|${rightUri}`;
          if (seen.has(k)) continue;
          seen.add(k);
          rows.push({
            relation_uri: r.relation_uri,
            relation_label: r.relation_label,
            domain_uri: leftUri,
            domain_label: isAtoB ? r.domain_label : r.range_label,
            domain_properties: propMapA.get(leftUri) ?? {},
            range_uri: rightUri,
            range_label: isAtoB ? r.range_label : r.domain_label,
            range_properties: propMapB.get(rightUri) ?? {},
          });
        }
        newPairRelations[`${classA}|${classB}`] = rows;
      }

      if (!cancelled) setPairRelations(newPairRelations);
    })();

    return () => { cancelled = true; };
  }, [selectedClassIds, selectedPairs, nodeInstances, workspaceId, activeGraph?.uri]);

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

  const isChainMode = selectedClassIds.length >= 2;
  const singleClassId = selectedClassIds[0];

  const selectionStats = useMemo(() => {
    const classes = selectedClassIds.length;
    const individuals = selectedClassIds.reduce(
      (sum, id) => sum + (nodeInstances[id]?.length ?? 0), 0
    );
    const relations = Object.values(filteredPairRelations).reduce(
      (sum, rows) => sum + rows.length, 0
    );
    const properties = selectedClassIds.reduce(
      (sum, id) => sum + (nodeInstances[id] ?? []).reduce(
        (s, inst) => s + Object.keys(inst.properties).length, 0
      ), 0
    );
    const rows = isChainMode
      ? chainTableRows.length
      : (nodeInstances[singleClassId]?.length ?? 0);
    return { classes, individuals, relations, properties, rows };
  }, [selectedClassIds, nodeInstances, filteredPairRelations, isChainMode, chainTableRows, singleClassId]);

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
          edges={displayEdges}
          selectedNodeId={selectedClassIds[0] ?? null}
          selectedEdgeIds={selectedEdgeIds}
          onNodeSelect={handleNodeSelect}
          onEdgeSelect={handleEdgeSelect}
          physicsEnabled={true}
          stabilizeKey={stabilizeKey}
          viewportLayoutKey={selectedClassIds.length > 0 ? `sel:${selectedClassIds[0]}/${displayNodes.length}` : undefined}
          fillContainer={true}
        />
        {relationPicker && (
          <RelationPickerDialog
            parentId={relationPicker.parentId}
            childId={relationPicker.nodeId}
            getClassLabel={getClassLabel}
            edges={relationPicker.edges}
            onPick={handleRelationPick}
            onCancel={() => setRelationPicker(null)}
          />
        )}
        {/* KPI cards overlay — hidden when a node is selected */}
        {!tableOpen && (
          <div className="absolute left-3 top-3 z-10 grid grid-cols-6 gap-3 w-[calc(100%-theme(spacing.6))] pointer-events-none">
            {kpis ? (
              <>
                <KpiCard label="Classes" value={kpis.classes.toLocaleString()} hint="Distinct rdf:type values (excluding OWL NamedIndividual)" icon={Network} className="pointer-events-auto" />
                <KpiCard label="Individuals" value={kpis.individuals.toLocaleString()} hint="Unique OWL NamedIndividuals in this graph" icon={Users} className="pointer-events-auto" />
                <KpiCard label="Relations" value={kpis.relations.toLocaleString()} hint="Object property links between individuals" icon={GitBranch} className="pointer-events-auto" />
                <KpiCard label="Properties" value={kpis.properties.toLocaleString()} hint="Literal data values attached to individuals" icon={Tag} className="pointer-events-auto" />
              </>
            ) : (
              <>
                <div className="border border-border/60 bg-card animate-pulse h-[110px]" />
                <div className="border border-border/60 bg-card animate-pulse h-[110px]" />
                <div className="border border-border/60 bg-card animate-pulse h-[110px]" />
                <div className="border border-border/60 bg-card animate-pulse h-[110px]" />
              </>
            )}
          </div>
        )}
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
              {isChainMode
                ? chainOrder.map(getClassLabel).join(' × ')
                : getClassLabel(singleClassId)}
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
              onClick={clearSelection}
              className="ml-auto rounded p-0.5 hover:bg-muted transition-colors"
              title="Close table"
            >
              <X size={14} />
            </button>
          </div>

          {/* Table content */}
          <div className="flex-1 overflow-hidden flex flex-col px-4 py-3">
            {tableLoading && Object.keys(nodeInstances).length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : isChainMode ? (
              <GraphNodeTable
                mode="chain"
                chainClassLabels={chainOrder.map(getClassLabel)}
                chainPairs={selectedPairs}
                chainRows={chainTableRows}
                chainSelectedPropUrisPerClass={chainOrder.map((classId) =>
                  (selectedPropUris[classId] ?? [RDFS_LABEL]).filter((u) => u !== RDFS_LABEL)
                )}
                statsSlot={<SelectionStats stats={selectionStats} />}
              />
            ) : (
              <GraphNodeTable
                mode="single"
                classLabel={getClassLabel(singleClassId)}
                instances={nodeInstances[singleClassId] ?? []}
                domainSelectedPropUris={(selectedPropUris[singleClassId] ?? [RDFS_LABEL]).filter((u) => u !== RDFS_LABEL)}
                statsSlot={<SelectionStats stats={selectionStats} />}
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
  const workspaceId = params.workspaceId as string;

  const {
    selectedGraphId,
    visibleGraphIds,
  } = useKnowledgeGraphStore();

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [graphsError, setGraphsError] = useState<string | null>(null);
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

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <GraphDevBanner />
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
