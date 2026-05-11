'use client';

import { useCallback, useMemo } from 'react';
import { type Node, type Edge } from 'vis-network/standalone';
import 'vis-network/styles/vis-network.css';
import type { GraphNode, GraphEdge } from '@/stores/knowledge-graph';
import { resolveBucketColors } from '@/lib/bfo';
import {
  EDGE_COLORS,
  DEFAULT_NODE_BOX_WIDTH,
  DEFAULT_NODE_BOX_HEIGHT,
  computeHierarchicalPositions,
  nodeCardSvgDataUri,
  wrapLabelTwoLines,
} from './layout';
import { useNodeLogos } from './use-node-logos';
import { useVisNetwork } from './use-vis-network';

interface VisNetworkProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
  onEdgeSelect: (edgeId: string | null) => void;
  stabilizeKey?: number;
  layoutDirection?: 'LR' | 'TD';
  /**
   * Stable id for the current graph "mode" (e.g. ontology relation toggles).
   * When this changes before the canvas updates, the previous zoom/pan is stored
   * and reapplied when returning to that mode.
   */
  viewStateKey?: string;
  /**
   * When true (and not in hierarchical layout), physics stays continuously
   * enabled instead of freezing after stabilization. Set by the parent when
   * filters that benefit from a live force-directed layout are active
   * (e.g. Restrictions / Object Properties).
   */
  physicsEnabled?: boolean;
  /**
   * When set to a node id, the canvas pans to center on that node's current
   * position, preserving the current zoom level. Triggers on every change
   * (null → id, or id → different id).
   */
  centerOnNodeId?: string | null;
}

/**
 * Thin orchestrator over the canvas runtime.
 *
 *  - `useNodeLogos` resolves node logos to data URIs (async).
 *  - `useVisNetwork` owns the vis-network instance, position memory, and viewport memory.
 *  - This component just builds `toVisNode` / `toVisEdge` (which close over logo cache
 *    and hierarchical positions) and renders the canvas container + scoped styles.
 */
export function VisNetwork({
  nodes,
  edges,
  selectedNodeId,
  onNodeSelect,
  onEdgeSelect,
  stabilizeKey,
  layoutDirection,
  viewStateKey,
  physicsEnabled = false,
  centerOnNodeId,
}: VisNetworkProps) {
  const { logoDataByUrl, getNodeLogoUrl } = useNodeLogos(nodes);

  const nodesByIri = useMemo(() => {
    const map = new Map<string, GraphNode>();
    for (const n of nodes) map.set(n.id, n);
    return map;
  }, [nodes]);

  const hierarchicalPositions = useMemo(
    () => (layoutDirection ? computeHierarchicalPositions(nodes, edges, layoutDirection) : null),
    [layoutDirection, nodes, edges],
  );

  const toVisNode = useCallback(
    (node: GraphNode): Node => {
      const colors = resolveBucketColors(node, nodesByIri);
      const logoUrl = getNodeLogoUrl(node);
      const wrapped = wrapLabelTwoLines(node.label);
      const logoDataUri = logoUrl ? logoDataByUrl[logoUrl] : undefined;
      const image = nodeCardSvgDataUri({
        width: DEFAULT_NODE_BOX_WIDTH,
        height: DEFAULT_NODE_BOX_HEIGHT,
        background: colors.background,
        border: colors.border,
        label: wrapped,
        logoDataUri,
      });

      const hierPos = hierarchicalPositions?.get(node.id);
      return {
        id: node.id,
        label: '',
        title: `${node.type}\n${node.label}`,
        shape: 'image',
        image,
        shapeProperties: { useImageSize: true, interpolation: true, coordinateOrigin: 'center' },
        x: hierPos?.x ?? node.x,
        y: hierPos?.y ?? node.y,
      };
    },
    [getNodeLogoUrl, logoDataByUrl, nodesByIri, hierarchicalPositions],
  );

  const toVisEdge = useCallback((edge: GraphEdge): Edge => {
    const isHierarchical = edge.properties?.relation_kind === 'is_a';
    const color = isHierarchical ? '#000000' : EDGE_COLORS[edge.type] || '#94a3b8';
    return {
      id: edge.id,
      from: edge.source,
      to: edge.target,
      label: isHierarchical ? undefined : edge.label || edge.type,
      title: edge.type,
      color: { color, highlight: color, hover: color },
      arrows: { to: { enabled: true, scaleFactor: 0.8 } },
      font: {
        size: 9,
        color: isHierarchical ? '#000000' : '#64748b',
        face: 'Inter, sans-serif',
        align: 'middle',
        background: '#ffffff',
      },
      smooth: { enabled: false, type: 'continuous', roundness: 0 },
      width: edge.weight || (isHierarchical ? 1 : 2),
      dashes: isHierarchical,
    };
  }, []);

  const { containerRef } = useVisNetwork({
    nodes,
    edges,
    selectedNodeId,
    onNodeSelect,
    onEdgeSelect,
    stabilizeKey,
    layoutDirection,
    viewStateKey,
    physicsEnabled,
    centerOnNodeId,
    toVisNode,
    toVisEdge,
  });

  return (
    <>
      <style jsx global>{`
        /* Style vis-network navigation buttons to match platform */
        .vis-navigation {
          position: absolute !important;
          bottom: 16px !important;
          right: 16px !important;
          left: auto !important;
          top: auto !important;
        }
        .vis-button {
          width: 32px !important;
          height: 32px !important;
          background-color: hsl(var(--card)) !important;
          border: 1px solid hsl(var(--border)) !important;
          border-radius: 8px !important;
          box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1) !important;
          background-size: 16px 16px !important;
          background-position: center !important;
          margin: 2px !important;
          cursor: pointer !important;
        }
        .vis-button:hover {
          background-color: hsl(var(--accent)) !important;
        }
        .vis-button.vis-up,
        .vis-button.vis-down,
        .vis-button.vis-left,
        .vis-button.vis-right {
          display: none !important; /* Hide pan buttons, keep zoom */
        }
        .vis-button.vis-zoomIn {
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='12' y1='5' x2='12' y2='19'%3E%3C/line%3E%3Cline x1='5' y1='12' x2='19' y2='12'%3E%3C/line%3E%3C/svg%3E") !important;
        }
        .vis-button.vis-zoomOut {
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='5' y1='12' x2='19' y2='12'%3E%3C/line%3E%3C/svg%3E") !important;
        }
        .vis-button.vis-zoomExtends {
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='15 3 21 3 21 9'%3E%3C/polyline%3E%3Cpolyline points='9 21 3 21 3 15'%3E%3C/polyline%3E%3Cline x1='21' y1='3' x2='14' y2='10'%3E%3C/line%3E%3Cline x1='3' y1='21' x2='10' y2='14'%3E%3C/line%3E%3C/svg%3E") !important;
        }
      `}</style>
      <div ref={containerRef} className="h-full w-full" style={{ minHeight: '400px' }} />
    </>
  );
}

// Re-export so existing call sites importing from `@/components/graph/vis-network`
// continue to work; the canonical definition lives in `@/lib/bfo`.
export { BFO_BUCKET_DEFS } from '@/lib/bfo';
export { BFOBucketFilters, BFOLegend } from './bfo-panels';
