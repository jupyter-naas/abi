'use client';

import { useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { GraphEdge, GraphNode } from '@/stores/knowledge-graph';
import { Maximize2 } from 'lucide-react';
import { individualHref } from '@/lib/graph-instance-browser';
import { explorerQuery } from '@/lib/graph-explorer';
import { instanceDomainGraph, instanceDomainRelationsKey, termEgoGraph, type InstanceRelation } from '@/lib/detail-network';
import { termNetworkRoute, termRoute } from '@/lib/ontology-navigation';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { INSTANCE_EGO_NODE_SPACING, InstanceNetworkCanvas } from './instance-network-canvas';
import './detail-network.css';

export function DetailNetwork({
  nodes,
  edges,
  selectedNodeId,
  onNodeSelect,
  onNodeDoubleClick,
  viewStateKey,
  layout = 'preview',
  searchPlaceholder,
  onOpen,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onNodeSelect: (id: string | null) => void;
  onNodeDoubleClick?: (id: string) => void;
  viewStateKey: string;
  layout?: 'preview' | 'page';
  searchPlaceholder?: string;
  onOpen?: () => void;
}) {
  const pin = layout === 'preview';
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const nodesById = useMemo(() => new Map(nodes.map(node => [node.id, node])), [nodes]);
  const edge = pin ? undefined : edges.find(item => item.id === selectedEdgeId);
  return (
    <div className="graph-detail-network" data-layout={layout} aria-label="Network">
      <div className="graph-detail-network-canvas">
        <InstanceNetworkCanvas
          nodes={nodes}
          edges={edges}
          selectedNodeId={pin ? null : selectedNodeId}
          selectedEdgeIds={edge ? [edge.id] : []}
          onNodeSelect={id => { setSelectedEdgeId(null); onNodeSelect(id); }}
          onEdgeSelect={id => setSelectedEdgeId(id)}
          onNodeDoubleClick={pin ? undefined : onNodeDoubleClick}
          viewStateKey={viewStateKey}
          toolbar={layout === 'page'}
          searchPlaceholder={searchPlaceholder}
          nodeSpacing={INSTANCE_EGO_NODE_SPACING}
          minimumAutoFitScale={layout === 'page' ? 0.35 : 0.2}
          focusOnSelection={false}
          interactive={!pin}
        />
        {onOpen && (
          <button type="button" className="graph-detail-network-open" onClick={onOpen}>
            <span>
              <Maximize2 size={12} />
              Open Network
            </span>
          </button>
        )}
      </div>
      {edge && <div className="graph-detail-network-relation" role="status">
        <span>{nodesById.get(edge.source)?.label} → {edge.label} → {nodesById.get(edge.target)?.label}</span>
        <button type="button" aria-label="Close relationship" onClick={() => setSelectedEdgeId(null)}>×</button>
      </div>}
    </div>
  );
}

export function InstanceDetailNetwork({
  uri,
  label,
  classLabel,
  relations,
  workspaceId,
  graphUri,
  layout = 'preview',
}: {
  uri: string;
  label: string;
  classLabel?: string;
  relations: InstanceRelation[];
  workspaceId: string;
  graphUri: string;
  layout?: 'preview' | 'page';
}) {
  const router = useRouter();
  const query = useSearchParams().toString();
  const relationsKey = instanceDomainRelationsKey(relations);
  const graph = useMemo(
    () => instanceDomainGraph({ uri, label, class_label: classLabel }, relations),
    // Payload identity, not the array the parent reallocates on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [uri, label, classLabel, relationsKey],
  );
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  if (!graph.edges.length) {
    return layout === 'page'
      ? <p className="graph-detail-network-status" role="status">No connections to show in this network.</p>
      : null;
  }
  const open = (id: string) => {
    if (id === graph.rootId) return;
    router.push(individualHref(workspaceId, graphUri, '', id));
  };
  const openNetworkTab = () => {
    router.replace(`?${explorerQuery(query, { view: 'network' })}`, { scroll: false });
  };
  return (
    <DetailNetwork
      nodes={graph.nodes}
      edges={graph.edges}
      selectedNodeId={selectedNodeId}
      onNodeSelect={setSelectedNodeId}
      onNodeDoubleClick={open}
      viewStateKey={`instance:${graphUri}:${uri}:${layout}`}
      layout={layout}
      onOpen={layout === 'preview' ? openNetworkTab : undefined}
    />
  );
}

export function TermDetailNetwork({
  term,
  terms,
  basePath,
  layout = 'preview',
}: {
  term: DictionaryTerm;
  terms: DictionaryTerm[];
  basePath?: string;
  layout?: 'preview' | 'page';
}) {
  const router = useRouter();
  const params = useSearchParams();
  const graph = useMemo(() => termEgoGraph(term, terms), [term, terms]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  if (!graph.edges.length) {
    return layout === 'page'
      ? <div className="graph-detail-network-page"><p className="graph-detail-network-status" role="status">No connections to show in this network.</p></div>
      : null;
  }
  const open = (id: string) => {
    if (id === graph.rootId) return;
    const target = terms.find(item => `${item.type}:${item.id}` === id);
    if (!target) return;
    const next = termRoute(basePath ? 'view=classes' : params?.toString() || '', target);
    next.set('browser', 'dictionary');
    router.push(`${basePath || ''}?${next}`, { scroll: false });
  };
  const openNetworkTab = () => {
    const next = termNetworkRoute(basePath ? 'view=classes' : params?.toString() || '', term);
    const href = `${basePath || ''}?${next}`;
    if (basePath) router.push(href, { scroll: false });
    else router.replace(`?${next}`, { scroll: false });
  };
  const body = (
    <DetailNetwork
      nodes={graph.nodes}
      edges={graph.edges}
      selectedNodeId={selectedNodeId}
      onNodeSelect={setSelectedNodeId}
      onNodeDoubleClick={open}
      viewStateKey={`term:${term.type}:${term.id}:${layout}`}
      layout={layout}
      searchPlaceholder="Search terms…"
      onOpen={layout === 'preview' ? openNetworkTab : undefined}
    />
  );
  return layout === 'page' ? <div className="graph-detail-network-page">{body}</div> : body;
}
