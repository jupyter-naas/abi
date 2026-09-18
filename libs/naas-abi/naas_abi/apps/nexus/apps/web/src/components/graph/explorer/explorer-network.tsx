'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import type { GraphEdge, GraphNode } from '@/stores/knowledge-graph';
import type { ApiDiscoveryInstance } from '../individuals-table';

export const preloadExplorerNetwork = () => import('../vis-network');

const VisNetwork = dynamic(() => preloadExplorerNetwork().then(module => module.VisNetwork), {
  ssr: false,
  loading: () => <p className="graph-explorer-message" role="status">Loading network…</p>,
});

export interface ExplorerNetworkData {
  items: ApiDiscoveryInstance[];
  has_more: boolean;
  neighbors?: Array<Omit<ApiDiscoveryInstance, 'properties'>>;
  relations?: Array<{ graph_uri: string; source: string; target: string; predicate: string; label: string }>;
  relations_truncated?: boolean;
}

const resourceId = (graph: string, uri: string) => JSON.stringify([graph, uri]);

export function ExplorerNetwork({ data, selected, onSelect, scopeKey }: {
  data: ExplorerNetworkData;
  selected: ApiDiscoveryInstance | null;
  onSelect: (instance: ApiDiscoveryInstance | null) => void;
  scopeKey: string;
}) {
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const model = useMemo(() => {
    const resources = new Map<string, ApiDiscoveryInstance>();
    for (const instance of [...data.items, ...(data.neighbors || [])]) {
      if (instance.graph_uri) resources.set(resourceId(instance.graph_uri, instance.uri), { properties: {}, ...instance });
    }
    const nodes: GraphNode[] = [...resources].map(([id, instance]) => ({
      id, label: instance.label || instance.uri, type: instance.class_label || 'Resource',
      properties: { uri: instance.uri, graph_uri: instance.graph_uri, class_uri: instance.class_uri },
    }));
    const edges: GraphEdge[] = (data.relations || []).map(relation => ({
      id: JSON.stringify([relation.graph_uri, relation.source, relation.predicate, relation.target]),
      source: resourceId(relation.graph_uri, relation.source),
      target: resourceId(relation.graph_uri, relation.target),
      type: relation.predicate, label: relation.label,
    }));
    return { nodes, edges, resources };
  }, [data]);
  const edge = model.edges.find(item => item.id === selectedEdgeId);
  return <div className="graph-explorer-network">
    <VisNetwork
      nodes={model.nodes} edges={model.edges}
      selectedNodeId={selected?.graph_uri ? resourceId(selected.graph_uri, selected.uri) : null}
      selectedEdgeIds={edge ? [edge.id] : []}
      onNodeSelect={id => { setSelectedEdgeId(null); onSelect(id ? model.resources.get(id) || null : null); }}
      onEdgeSelect={id => setSelectedEdgeId(id)}
      zoomOnDoubleClick focusOnSelection preserveZoomOnResize preserveZoomOnSelection
      fillContainer nodeSpacing={60} minimumAutoFitScale={0.35} viewStateKey={scopeKey}
    />
    {edge && <div className="graph-explorer-network-relation" role="status">
      <span>{model.resources.get(edge.source)?.label} → {edge.label} → {model.resources.get(edge.target)?.label}</span>
      <button type="button" aria-label="Close relationship" onClick={() => setSelectedEdgeId(null)}>×</button>
    </div>}
  </div>;
}
