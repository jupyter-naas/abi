'use client';

import { useCallback, useEffect, useLayoutEffect, useRef } from 'react';
import {
  Network,
  DataSet,
  type Options,
  type Node,
  type Edge,
} from 'vis-network/standalone';
import 'vis-network/styles/vis-network.css';
import type { GraphNode, GraphEdge } from '@/stores/knowledge-graph';
import { computeSpreadPositions } from './layout';

export interface UseVisNetworkArgs {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
  onEdgeSelect: (edgeId: string | null) => void;
  /** Bumped from the parent to request a re-stabilization (filters, parents toggled, …). */
  stabilizeKey?: number;
  /** When set, switches to a baked hierarchical layout in that orientation. */
  layoutDirection?: 'LR' | 'TD';
  /** Stable id for the current "mode" — used to remember zoom/pan per mode. */
  viewStateKey?: string;
  /** When true (and not hierarchical), keep physics live instead of freezing. */
  physicsEnabled?: boolean;
  /** Pan to centre this node on every change; preserves current zoom. */
  centerOnNodeId?: string | null;
  /** Maps a `GraphNode` to a vis-network `Node`. Closes over logo cache + positions. */
  toVisNode: (node: GraphNode) => Node;
  /** Maps a `GraphEdge` to a vis-network `Edge`. */
  toVisEdge: (edge: GraphEdge) => Edge;
}

export interface UseVisNetworkResult {
  containerRef: React.RefObject<HTMLDivElement>;
}

const NETWORK_OPTIONS: Options = {
  autoResize: true,
  height: '100%',
  width: '100%',
  nodes: {
    shape: 'image',
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
    navigationButtons: true,
    keyboard: { enabled: true, bindToWindow: false },
    zoomView: true,
    dragView: true,
  },
  layout: {
    improvedLayout: false,
  },
};

/**
 * Encapsulates the vis-network canvas runtime: instance lifecycle, position
 * memory, viewport (zoom/pan) memory per `viewStateKey`, physics toggling,
 * incremental DataSet updates, selection, and centering.
 *
 * Design notes:
 *  - Effects and their dep arrays match the inline implementation exactly.
 *    This is intentional — the canvas is timing-sensitive and any reordering
 *    of stabilization / fit / physics-toggle steps is a regression risk.
 *  - `toVisNode` / `toVisEdge` are passed in (not constructed here) because
 *    they close over external state (logo cache, hierarchical positions).
 */
export function useVisNetwork({
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
  toVisNode,
  toVisEdge,
}: UseVisNetworkArgs): UseVisNetworkResult {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const nodesDataRef = useRef<DataSet<Node>>(new DataSet());
  const edgesDataRef = useRef<DataSet<Edge>>(new DataSet());
  const onNodeSelectRef = useRef(onNodeSelect);
  const onEdgeSelectRef = useRef(onEdgeSelect);
  const prevSelectedNodeIdRef = useRef<string | null>(null);

  // ── Viewport (zoom/pan) memory per filter/view key ─────────────────────────
  const savedFilterViewsRef = useRef(
    new Map<string, { scale: number; position: { x: number; y: number } }>(),
  );
  const prevFilterViewKeyRef = useRef<string | undefined>(undefined);
  const currentFilterViewKeyRef = useRef<string>('__default');
  /** True after filter key changed: next graph update should restore or fit for the new key. */
  const pendingFilterViewportApplyRef = useRef(false);

  /** Restore saved zoom/pan for `currentFilterViewKeyRef`, or fit if unseen. */
  const applySavedViewportOrFit = useCallback((opts?: { fitDurationMs?: number }) => {
    const net = networkRef.current;
    if (!net || nodesDataRef.current.length === 0) return;
    const key = currentFilterViewKeyRef.current;
    const saved = savedFilterViewsRef.current.get(key);
    const fitDurationMs = opts?.fitDurationMs ?? 300;
    if (saved) {
      try {
        net.moveTo({
          scale: saved.scale,
          position: saved.position,
          animation: { duration: 0, easingFunction: 'linear' },
        });
        return;
      } catch {
        // fallthrough to fit
      }
    }
    net.fit({ animation: { duration: fitDurationMs, easingFunction: 'easeInOutQuad' } });
  }, []);

  // Capture viewport for outgoing key, mark inbound key as pending apply.
  // Runs in layout effect so the capture happens before the canvas paints.
  useLayoutEffect(() => {
    const key = viewStateKey ?? '__default';
    const net = networkRef.current;
    const prevKey = prevFilterViewKeyRef.current;
    if (net && prevKey !== undefined && prevKey !== key) {
      try {
        savedFilterViewsRef.current.set(prevKey, {
          scale: net.getScale(),
          position: net.getViewPosition(),
        });
      } catch {
        // Ignore read errors during teardown / empty graph.
      }
      pendingFilterViewportApplyRef.current = true;
    }
    prevFilterViewKeyRef.current = key;
    currentFilterViewKeyRef.current = key;
  }, [viewStateKey]);

  // Keep selection callbacks fresh without re-binding the click handler.
  useEffect(() => {
    onNodeSelectRef.current = onNodeSelect;
    onEdgeSelectRef.current = onEdgeSelect;
  }, [onNodeSelect, onEdgeSelect]);

  // ── Network instance lifecycle ─────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    networkRef.current = new Network(
      containerRef.current,
      { nodes: nodesDataRef.current, edges: edgesDataRef.current },
      NETWORK_OPTIONS,
    );

    networkRef.current.on('click', (params) => {
      if (params.nodes.length > 0) {
        onNodeSelectRef.current(params.nodes[0] as string);
      } else if (params.edges.length > 0) {
        onEdgeSelectRef.current(params.edges[0] as string);
      } else {
        onNodeSelectRef.current(null);
        onEdgeSelectRef.current(null);
      }
    });

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, []);

  // ── Position memory & physics state ────────────────────────────────────────
  const isStabilizedRef = useRef(false);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  /** Last `layoutDirection` from the nodes effect — used to detect leaving hierarchical layout. */
  const prevLayoutDirectionRef = useRef<'LR' | 'TD' | undefined>(undefined);
  /**
   * Mirror of the `physicsEnabled` prop, readable from inside async vis-network
   * event callbacks (`stabilizationIterationsDone`) where the closure-captured
   * prop value would be stale.
   */
  const physicsEnabledRef = useRef(physicsEnabled);
  useEffect(() => {
    physicsEnabledRef.current = physicsEnabled;
  }, [physicsEnabled]);

  // Toggle live physics when the prop changes. Hierarchical layout is always
  // physics-off (positions are baked in), so this is a no-op there.
  useEffect(() => {
    const net = networkRef.current;
    if (!net) return;
    if (layoutDirection) return;
    if (physicsEnabled) {
      net.setOptions({ physics: { enabled: true } });
      return;
    }
    // Disabling: capture positions so they survive future updates / context switches.
    const positions = net.getPositions();
    Object.entries(positions).forEach(([id, pos]) => {
      nodePositionsRef.current.set(id, pos as { x: number; y: number });
    });
    net.setOptions({ physics: { enabled: false } });
  }, [physicsEnabled, layoutDirection]);

  // ── Update nodes (the big one) ─────────────────────────────────────────────
  useEffect(() => {
    const prevLayoutDir = prevLayoutDirectionRef.current;
    const exitedHierarchicalLayout = prevLayoutDir !== undefined && layoutDirection === undefined;

    const seenIds = new Set<string>();
    const uniqueNodes = nodes.filter((node) => {
      if (seenIds.has(node.id)) return false;
      seenIds.add(node.id);
      return true;
    });

    try {
      if (layoutDirection) {
        // Hierarchical layout: positions are baked into toVisNode via hierarchicalPositions.
        // Disable physics and fit the view to the positioned graph.
        nodesDataRef.current.clear();
        nodesDataRef.current.add(uniqueNodes.map(toVisNode));
        if (networkRef.current && uniqueNodes.length > 0) {
          networkRef.current.setOptions({ physics: { enabled: false } });
          if (pendingFilterViewportApplyRef.current) {
            pendingFilterViewportApplyRef.current = false;
            applySavedViewportOrFit({ fitDurationMs: 500 });
          } else {
            networkRef.current.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
          }
        }
        isStabilizedRef.current = true;
        return;
      }

      // SubclassOf / hierarchy layout turned off: force a fresh force-directed pass.
      if (exitedHierarchicalLayout && networkRef.current) {
        isStabilizedRef.current = false;
        // Drop baked coordinates so ForceAtlas2 lays out from scratch, not the hierarchy positions.
        nodePositionsRef.current.clear();
        networkRef.current.setOptions({ physics: { enabled: true } });
      }

      if (isStabilizedRef.current && networkRef.current) {
        const livePositions = networkRef.current.getPositions();
        Object.entries(livePositions).forEach(([id, pos]) => {
          nodePositionsRef.current.set(id, pos as { x: number; y: number });
        });

        // Bounding box for placing new nodes above the existing layout.
        // Linear loop avoids `Math.min(...arr)` call-stack overflow on huge graphs.
        let minY = Infinity,
          minX = Infinity,
          maxX = -Infinity,
          sumX = 0,
          count = 0;
        for (const p of nodePositionsRef.current.values()) {
          if (p.y < minY) minY = p.y;
          if (p.x < minX) minX = p.x;
          if (p.x > maxX) maxX = p.x;
          sumX += p.x;
          count++;
        }
        if (count === 0) {
          minY = 0;
          minX = 0;
          maxX = 0;
        }
        const avgX = count > 0 ? sumX / count : 0;
        const xSpread = count > 0 ? maxX - minX : 600;

        const existingIds = new Set(nodesDataRef.current.getIds() as string[]);
        const incomingIds = new Set(uniqueNodes.map((n) => n.id));

        const removedIds = [...existingIds].filter((id) => !incomingIds.has(id));
        if (removedIds.length > 0) nodesDataRef.current.remove(removedIds);

        const toUpdate: Node[] = [];
        const toAdd: Node[] = [];
        let newIdx = 0;
        for (const node of uniqueNodes) {
          const base = toVisNode(node);
          const saved = nodePositionsRef.current.get(node.id);
          if (existingIds.has(node.id)) {
            // Keep current position — overwrite with saved coords to prevent vis-network drift.
            toUpdate.push({ ...base, x: saved?.x, y: saved?.y });
          } else {
            // New node (e.g. a loaded parent): place it in a row above existing nodes.
            const col = newIdx % 5;
            const row = Math.floor(newIdx / 5);
            const newX = avgX + (col - 2) * (xSpread / 4 + 150);
            const newY = minY - 350 - row * 180;
            toAdd.push({ ...base, x: newX, y: newY });
            newIdx++;
          }
        }
        if (toUpdate.length > 0) nodesDataRef.current.update(toUpdate);
        if (toAdd.length > 0) nodesDataRef.current.add(toAdd);
        if (pendingFilterViewportApplyRef.current && networkRef.current) {
          pendingFilterViewportApplyRef.current = false;
          requestAnimationFrame(() => applySavedViewportOrFit({ fitDurationMs: 300 }));
        }
        return;
      }

      // Initial load — full clear + add, then let physics stabilize.
      // Pre-spread nodes without a saved position using a sunflower spiral so
      // physics starts from a distributed layout rather than piling up at the origin.
      const unsavedIds = uniqueNodes
        .filter((n) => !nodePositionsRef.current.has(n.id))
        .map((n) => n.id);
      const spreadPositions = computeSpreadPositions(unsavedIds);

      const visNodes = uniqueNodes.map((node) => {
        const baseNode = toVisNode(node);
        const savedPos = nodePositionsRef.current.get(node.id);
        if (savedPos) return { ...baseNode, x: savedPos.x, y: savedPos.y };
        const initPos = spreadPositions.get(node.id);
        if (initPos) return { ...baseNode, x: initPos.x, y: initPos.y };
        return baseNode;
      });

      nodesDataRef.current.clear();
      nodesDataRef.current.add(visNodes);

      if (networkRef.current && visNodes.length > 0) {
        networkRef.current.once('stabilizationIterationsDone', () => {
          if (networkRef.current) {
            const positions = networkRef.current.getPositions();
            Object.entries(positions).forEach(([id, pos]) => {
              nodePositionsRef.current.set(id, pos as { x: number; y: number });
            });
            isStabilizedRef.current = true;
            if (!physicsEnabledRef.current) {
              networkRef.current.setOptions({ physics: { enabled: false } });
            }
            if (pendingFilterViewportApplyRef.current) {
              pendingFilterViewportApplyRef.current = false;
              applySavedViewportOrFit({ fitDurationMs: 500 });
            } else {
              networkRef.current.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
            }
          }
        });
        if (exitedHierarchicalLayout) {
          networkRef.current.stabilize(200);
        }
      }
    } finally {
      prevLayoutDirectionRef.current = layoutDirection;
    }
  }, [nodes, toVisNode, layoutDirection, applySavedViewportOrFit]);

  // Fallback: if no other code path consumes `pendingFilterViewportApplyRef`
  // this frame (e.g. edges-only refresh), still restore viewport once the
  // graph settles.
  useEffect(() => {
    if (!pendingFilterViewportApplyRef.current) return;
    const timer = window.setTimeout(() => {
      if (
        !pendingFilterViewportApplyRef.current ||
        !networkRef.current ||
        nodesDataRef.current.length === 0
      ) {
        return;
      }
      pendingFilterViewportApplyRef.current = false;
      applySavedViewportOrFit({ fitDurationMs: 300 });
    }, 420);
    return () => clearTimeout(timer);
  }, [
    viewStateKey,
    nodes.length,
    edges.length,
    layoutDirection,
    applySavedViewportOrFit,
  ]);

  // ── Update edges ───────────────────────────────────────────────────────────
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

  // Re-run physics when stabilizeKey changes (bucket filter, relations, parents toggled).
  // Skip in hierarchical layout — positions are already fixed.
  useEffect(() => {
    if (stabilizeKey === undefined || stabilizeKey === 0) return;
    if (!networkRef.current || layoutDirection) return;
    isStabilizedRef.current = false;
    networkRef.current.setOptions({ physics: { enabled: true } });
    networkRef.current.once('stabilizationIterationsDone', () => {
      if (!networkRef.current) return;
      const positions = networkRef.current.getPositions();
      Object.entries(positions).forEach(([id, pos]) => {
        nodePositionsRef.current.set(id, pos as { x: number; y: number });
      });
      isStabilizedRef.current = true;
      if (!physicsEnabledRef.current) {
        networkRef.current.setOptions({ physics: { enabled: false } });
      }
    });
    networkRef.current.stabilize(200);
  }, [stabilizeKey, layoutDirection]);

  // Selection: visually select and pan to centre, preserving zoom.
  // Double-RAF lets the canvas finish resizing (inspector open/close) before pan.
  useEffect(() => {
    if (!networkRef.current) return;

    const hadSelected = prevSelectedNodeIdRef.current !== null;
    prevSelectedNodeIdRef.current = selectedNodeId;

    let cancelled = false;

    if (!selectedNodeId) {
      if (!hadSelected) return;
      requestAnimationFrame(() => {
        if (cancelled) return;
        requestAnimationFrame(() => {
          if (cancelled || !networkRef.current || nodesDataRef.current.length === 0) return;
          networkRef.current.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
        });
      });
      return () => {
        cancelled = true;
      };
    }

    if (!nodesDataRef.current.get(selectedNodeId)) return;
    networkRef.current.selectNodes([selectedNodeId]);

    requestAnimationFrame(() => {
      if (cancelled) return;
      requestAnimationFrame(() => {
        if (cancelled || !networkRef.current) return;
        const currentScale = networkRef.current.getScale();
        const targetScale = Math.max(currentScale, 1.35);
        networkRef.current.focus(selectedNodeId, {
          scale: targetScale,
          animation: { duration: 300, easingFunction: 'easeInOutQuad' },
        });
      });
    });

    return () => {
      cancelled = true;
    };
  }, [selectedNodeId]);

  // Fit all visible nodes when focus mode activates.
  useEffect(() => {
    if (!centerOnNodeId || !networkRef.current) return;
    const net = networkRef.current;
    let cancelled = false;
    requestAnimationFrame(() => {
      if (cancelled) return;
      requestAnimationFrame(() => {
        if (cancelled || !net) return;
        net.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
      });
    });
    return () => {
      cancelled = true;
    };
  }, [centerOnNodeId]);

  return { containerRef };
}
