'use client';

import { useEffect, useRef, useCallback } from 'react';
import { Network, DataSet, type Options, type Node, type Edge } from 'vis-network/standalone';
import 'vis-network/styles/vis-network.css';
import type { GraphNode, GraphEdge } from '@/stores/knowledge-graph';

// BFO 7 Buckets color scheme (simplified)
const BFO_COLORS = {
  'Material Entity': { background: '#3b82f6', border: '#2563eb', highlight: '#60a5fa' },
  'Process': { background: '#22c55e', border: '#16a34a', highlight: '#4ade80' },
  'Temporal Region': { background: '#a855f7', border: '#9333ea', highlight: '#c084fc' },
  'Site': { background: '#f97316', border: '#ea580c', highlight: '#fb923c' },
  'Quality': { background: '#ec4899', border: '#db2777', highlight: '#f472b6' },
  'Realizable': { background: '#eab308', border: '#ca8a04', highlight: '#facc15' },
  // Role and Disposition are both Realizables - map to same color
  'Role': { background: '#eab308', border: '#ca8a04', highlight: '#facc15' },
  'Disposition': { background: '#eab308', border: '#ca8a04', highlight: '#facc15' },
  'GDC': { background: '#06b6d4', border: '#0891b2', highlight: '#22d3ee' },
  'Entity': { background: '#6b7280', border: '#4b5563', highlight: '#9ca3af' },
};

const EDGE_COLORS: Record<string, string> = {
  'participates in': '#22c55e',
  'has participant': '#22c55e',
  'occurs in': '#f97316',
  'located in': '#f97316',
  'bearer of': '#ec4899',
  'inheres in': '#ec4899',
  'has role': '#eab308',
  'has disposition': '#f59e0b',
  'realizes': '#a855f7',
  'precedes': '#8b5cf6',
  'preceded by': '#8b5cf6',
  'concretizes': '#06b6d4',
  'is carrier of': '#06b6d4',
  'generically depends on': '#06b6d4',
};

interface VisNetworkProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
  onEdgeSelect: (edgeId: string | null) => void;
}

export function VisNetwork({
  nodes,
  edges,
  selectedNodeId,
  onNodeSelect,
  onEdgeSelect,
}: VisNetworkProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const nodesDataRef = useRef<DataSet<Node>>(new DataSet());
  const edgesDataRef = useRef<DataSet<Edge>>(new DataSet());

  const toVisNode = useCallback((node: GraphNode): Node => {
    const colors = BFO_COLORS[node.type as keyof typeof BFO_COLORS] || BFO_COLORS['Entity'];
    return {
      id: node.id,
      label: node.label,
      title: `${node.type}\n${node.label}`,
      color: {
        background: colors.background,
        border: colors.border,
        highlight: { background: colors.highlight, border: colors.border },
      },
      font: { 
        color: '#1f2937', 
        size: 14, 
        face: 'Inter, sans-serif',
        strokeWidth: 3,
        strokeColor: '#ffffff',
      },
      shape: (node.properties?.shape as string) || 'dot',
      size: (node.properties?.size as number) || node.size || 25,
      x: node.x,
      y: node.y,
    };
  }, []);

  const toVisEdge = useCallback((edge: GraphEdge): Edge => {
    const color = EDGE_COLORS[edge.type] || '#94a3b8';
    return {
      id: edge.id,
      from: edge.source,
      to: edge.target,
      label: edge.label || edge.type,
      title: edge.type,
      color: { color, highlight: color, hover: color },
      arrows: { to: { enabled: true, scaleFactor: 0.8 } },
      font: { size: 10, color: '#64748b', face: 'Inter, sans-serif', align: 'middle' },
      smooth: { enabled: true, type: 'curvedCW', roundness: 0.2 },
      width: edge.weight || 2,
    };
  }, []);

  // Network options - simple config, let vis-network handle zoom
  const options: Options = {
    autoResize: true,
    height: '100%',
    width: '100%',
    nodes: {
      borderWidth: 2,
      shadow: { enabled: true, color: 'rgba(0,0,0,0.2)', size: 5, x: 2, y: 2 },
    },
    edges: {
      width: 2,
      selectionWidth: 3,
      shadow: { enabled: true, color: 'rgba(0,0,0,0.1)', size: 3, x: 1, y: 1 },
    },
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -120,
        centralGravity: 0.005,
        springLength: 250,
        springConstant: 0.04,
        damping: 0.5,
        avoidOverlap: 1,
      },
      stabilization: { enabled: true, iterations: 200, updateInterval: 25 },
      minVelocity: 0.75,
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      multiselect: true,
      navigationButtons: true,  // Enable built-in navigation buttons
      keyboard: { enabled: true, bindToWindow: false },
      zoomView: true,
      dragView: true,
    },
    layout: {
      improvedLayout: true,
      randomSeed: 42,
    },
  };

  // Initialize network once
  useEffect(() => {
    if (!containerRef.current) return;

    networkRef.current = new Network(
      containerRef.current,
      { nodes: nodesDataRef.current, edges: edgesDataRef.current },
      options
    );

    networkRef.current.on('click', (params) => {
      if (params.nodes.length > 0) {
        onNodeSelect(params.nodes[0] as string);
      } else if (params.edges.length > 0) {
        onEdgeSelect(params.edges[0] as string);
      } else {
        onNodeSelect(null);
        onEdgeSelect(null);
      }
    });

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, [onNodeSelect, onEdgeSelect]);

  // Track if initial stabilization is done
  const isStabilizedRef = useRef(false);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  // Update nodes
  useEffect(() => {
    const seenIds = new Set<string>();
    const uniqueNodes = nodes.filter((node) => {
      if (seenIds.has(node.id)) return false;
      seenIds.add(node.id);
      return true;
    });

    // If already stabilized, save current positions before updating
    if (isStabilizedRef.current && networkRef.current) {
      const positions = networkRef.current.getPositions();
      Object.entries(positions).forEach(([id, pos]) => {
        nodePositionsRef.current.set(id, pos as { x: number; y: number });
      });
    }

    // Map nodes with preserved positions
    const visNodes = uniqueNodes.map((node) => {
      const baseNode = toVisNode(node);
      const savedPos = nodePositionsRef.current.get(node.id);
      if (savedPos && isStabilizedRef.current) {
        return { ...baseNode, x: savedPos.x, y: savedPos.y };
      }
      return baseNode;
    });
    
    nodesDataRef.current.clear();
    nodesDataRef.current.add(visNodes);

    // Initial load: run physics then disable
    if (!isStabilizedRef.current && networkRef.current && visNodes.length > 0) {
      networkRef.current.once('stabilizationIterationsDone', () => {
        if (networkRef.current) {
          // Save positions after stabilization
          const positions = networkRef.current.getPositions();
          Object.entries(positions).forEach(([id, pos]) => {
            nodePositionsRef.current.set(id, pos as { x: number; y: number });
          });
          isStabilizedRef.current = true;
          networkRef.current.setOptions({ physics: { enabled: false } });
          networkRef.current.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
        }
      });
    } else if (isStabilizedRef.current && networkRef.current && visNodes.length > 0) {
      // Already stabilized: just fit without physics
      setTimeout(() => {
        if (networkRef.current) {
          networkRef.current.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
        }
      }, 50);
    }
  }, [nodes, toVisNode]);

  // Update edges
  useEffect(() => {
    const seenIds = new Set<string>();
    const uniqueEdges = edges.filter((edge) => {
      if (seenIds.has(edge.id)) return false;
      seenIds.add(edge.id);
      return true;
    });
    edgesDataRef.current.clear();
    edgesDataRef.current.add(uniqueEdges.map(toVisEdge));
  }, [edges, toVisEdge]);

  // Handle selected node
  useEffect(() => {
    if (networkRef.current && selectedNodeId) {
      networkRef.current.selectNodes([selectedNodeId]);
    }
  }, [selectedNodeId]);

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
        .vis-button.vis-up, .vis-button.vis-down, 
        .vis-button.vis-left, .vis-button.vis-right {
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
      <div
        ref={containerRef}
        className="h-full w-full"
        style={{ minHeight: '400px' }}
      />
    </>
  );
}

// Legend component
export function BFOLegend() {
  const buckets = [
    { type: 'Material Entity', label: 'WHO', description: 'Objects, people, organizations' },
    { type: 'Process', label: 'WHAT', description: 'Events, activities, changes' },
    { type: 'Temporal Region', label: 'WHEN', description: 'Time periods, instants' },
    { type: 'Site', label: 'WHERE', description: 'Locations, places' },
    { type: 'Quality', label: 'HOW IT IS', description: 'Properties, attributes' },
    { type: 'Realizable', label: 'WHY', description: 'Roles & dispositions (realizables)' },
    { type: 'GDC', label: 'HOW WE KNOW', description: 'Documents, data, plans' },
  ];

  return (
    <div className="absolute top-4 right-4 z-10 rounded-lg border bg-card/95 p-3 shadow-lg backdrop-blur-sm">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        BFO 7 Buckets
      </h4>
      <div className="grid grid-cols-2 gap-2">
        {buckets.map((bucket) => {
          const colors = BFO_COLORS[bucket.type as keyof typeof BFO_COLORS];
          return (
            <div key={bucket.type} className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: colors.background }} />
              <span className="text-xs"><strong>{bucket.label}</strong></span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
