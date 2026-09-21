'use client';

import { useCallback, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { Search, X } from 'lucide-react';
import { buildHoverTitle } from './vis-network';
import type { GraphEdge, GraphNode } from '@/stores/knowledge-graph';
import { filterInstanceNetwork } from '@/lib/graph-network-view';
import './instance-network-canvas.css';

const VisNetwork = dynamic(() => import('./vis-network').then(module => module.VisNetwork), {
  ssr: false,
  loading: () => <p className="instance-network-status" role="status">Loading network…</p>,
});

/** Ego-graph spacing for the instance Details pin and Network tab. */
export const INSTANCE_EGO_NODE_SPACING = 60;

export function InstanceNetworkCanvas({
  nodes,
  edges,
  selectedNodeId,
  selectedEdgeIds = [],
  onNodeSelect,
  onEdgeSelect,
  onNodeDoubleClick,
  viewStateKey,
  toolbar = true,
  searchPlaceholder = 'Search instances…',
  fillContainer = true,
  nodeSpacing,
  minimumAutoFitScale = 0.35,
  focusOnSelection = true,
  interactive = true,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  selectedEdgeIds?: string[];
  onNodeSelect: (id: string | null) => void;
  onEdgeSelect: (id: string | null) => void;
  onNodeDoubleClick?: (id: string) => void;
  viewStateKey: string;
  toolbar?: boolean;
  searchPlaceholder?: string;
  fillContainer?: boolean;
  nodeSpacing?: number;
  minimumAutoFitScale?: number;
  focusOnSelection?: boolean;
  interactive?: boolean;
}) {
  const [search, setSearch] = useState('');
  const filtered = useMemo(
    () => filterInstanceNetwork(nodes, edges, { search }),
    [nodes, edges, search],
  );

  const getNodeTitle = useCallback((node: GraphNode) => buildHoverTitle([
    ['label', node.label],
    ['type', node.type || 'Resource'],
    ['uri', String(node.properties?.uri || node.properties?.iri || node.id)],
  ]), []);

  return (
    <div className="instance-network-canvas">
      {toolbar && (
        <div className="instance-network-toolbar">
          <div className="instance-network-search">
            <Search size={14} className="text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder={searchPlaceholder}
              aria-label="Search this network"
            />
            {search && (
              <button type="button" onClick={() => setSearch('')} aria-label="Clear search">
                <X size={14} />
              </button>
            )}
          </div>
          {search && (
            <span className="instance-network-count">
              Showing {filtered.nodes.length} of {nodes.length}
            </span>
          )}
        </div>
      )}
      <VisNetwork
        nodes={filtered.nodes}
        edges={filtered.edges}
        selectedNodeId={selectedNodeId}
        selectedEdgeIds={selectedEdgeIds}
        onNodeSelect={onNodeSelect}
        onEdgeSelect={onEdgeSelect}
        onNodeDoubleClick={onNodeDoubleClick}
        zoomOnDoubleClick={interactive}
        focusOnSelection={focusOnSelection}
        preserveZoomOnResize
        preserveZoomOnSelection
        fillContainer={fillContainer}
        nodeSpacing={nodeSpacing ?? 80}
        minimumAutoFitScale={minimumAutoFitScale}
        viewStateKey={`${viewStateKey}|instance-circles`}
        orthogonalEdges={false}
        circularNodes
        labelPlacement="top"
        getNodeTitle={interactive ? getNodeTitle : undefined}
        interactive={interactive}
      />
    </div>
  );
}
