'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { BFO_BUCKET_BY_TYPE } from '@/lib/bfo-buckets';
import { EVENT_GRAPH_BUCKETS, UNKNOWN, type BfoBucketType } from './bfo-event-projection';
import type { EventGraphModel, GraphFilters } from './event-graph-model';
import type { GraphParams, GraphView } from './event-graph-params';
import { runPhysics, settlePhysicsSync } from './event-graph-physics';
import { EventGraphToolbar } from './event-graph-toolbar';
import { EventGraphParamsPanel } from './event-graph-params-panel';
import {
  depthAlpha,
  edgeGeometry,
  nodeLabelLines,
  nodeRadiusOf,
  pointOnQuadratic,
  projectNodes,
  seedEventGraph,
  tangentOnQuadratic,
  NODE_LABEL_FONT_SIZE,
  NODE_LABEL_LINE_HEIGHT,
  type LayoutEdge,
  type LayoutNode,
} from './event-graph-layout';

const DEFAULT_YAW = -0.6;
const DEFAULT_PITCH = 0.35;
const MIN_SCALE = 0.25;
const MAX_SCALE = 2.5;

interface CanvasColors {
  ink: string;
  muted: string;
  surface: string;
}

let cachedColors: { key: string; colors: CanvasColors } | null = null;

/** Canvas cannot read `hsl(var(--x))`, so the palette uses the hex mirrors. */
function readColors(): CanvasColors {
  const key = document.documentElement.className;
  if (cachedColors?.key === key) return cachedColors.colors;
  const style = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  const colors: CanvasColors = {
    ink: read('--foreground-hex', '#18181B'),
    muted: read('--muted-foreground-hex', '#71717A'),
    surface: read('--background-hex', '#FCFCFC'),
  };
  cachedColors = { key, colors };
  return colors;
}

function bucketPalette(node: LayoutNode): { color: string; border: string } {
  const def = BFO_BUCKET_BY_TYPE[node.bucket] ?? BFO_BUCKET_BY_TYPE.Unknown;
  if (node.known) return { color: def.color, border: def.border };
  // A gap keeps its bucket's ring so the reader still knows which one is empty.
  return { color: BFO_BUCKET_BY_TYPE.Unknown.color, border: def.border };
}

export function EventGraphCanvas({
  model,
  params,
  filters,
  searchValue,
  onParamChange,
  onSwitchView,
  onResetParams,
  onFiltersChange,
  onSearchChange,
  onPickProcess,
}: {
  model: EventGraphModel;
  params: GraphParams;
  filters: GraphFilters;
  searchValue: string;
  onParamChange: (key: string, value: string | number | boolean) => void;
  onSwitchView: (view: GraphView) => void;
  onResetParams: () => void;
  onFiltersChange: (next: GraphFilters) => void;
  onSearchChange: (value: string) => void;
  onPickProcess: (uri: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedIdRef = useRef<string | null>(null);
  const apiRef = useRef<{ draw: () => void; zoomBy: (factor: number) => void; reset: () => void } | null>(null);
  const pickRef = useRef(onPickProcess);
  pickRef.current = onPickProcess;

  const layout = useMemo(() => seedEventGraph(model, params), [model, params]);

  const selectedNode = useMemo(
    () => layout.nodes.find((node) => node.id === selectedId) ?? null,
    [layout, selectedId],
  );

  // The focus process is the reader's entry point into the shape.
  useEffect(() => {
    selectedIdRef.current = layout.focus?.id ?? null;
    setSelectedId(layout.focus?.id ?? null);
  }, [layout]);

  useEffect(() => {
    selectedIdRef.current = selectedId;
    apiRef.current?.draw();
  }, [selectedId]);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const view = params.view;
    const threeD = view === '3d';
    const orbit = { yaw: DEFAULT_YAW, pitch: DEFAULT_PITCH };
    const pan = { x: 0, y: 0 };
    let scale = params.zoom;
    let orbiting: { x: number; y: number; yaw: number; pitch: number } | null = null;
    let panning: { x: number; y: number } | null = null;
    let dragging: LayoutNode | null = null;
    let dragOffset = { x: 0, y: 0 };
    let pressed: { node: LayoutNode | null; x: number; y: number; moved: boolean } | null = null;

    const { nodes, edges } = layout;

    function drawEdgeLabel(text: string, x: number, y: number, colors: CanvasColors) {
      const fontSize = 10;
      ctx!.font = `${fontSize}px var(--font-body), system-ui, sans-serif`;
      const boxW = ctx!.measureText(text).width + 10;
      const boxH = fontSize + 6;
      ctx!.fillStyle = colors.surface;
      ctx!.fillRect(x - boxW / 2, y - boxH / 2, boxW, boxH);
      ctx!.fillStyle = colors.muted;
      ctx!.textAlign = 'center';
      ctx!.textBaseline = 'middle';
      ctx!.fillText(text, x, y);
    }

    function drawArrowhead(x: number, y: number, angle: number, size: number, color: string) {
      ctx!.beginPath();
      ctx!.moveTo(x, y);
      ctx!.lineTo(x - size * Math.cos(angle - Math.PI / 7), y - size * Math.sin(angle - Math.PI / 7));
      ctx!.lineTo(x - size * Math.cos(angle + Math.PI / 7), y - size * Math.sin(angle + Math.PI / 7));
      ctx!.closePath();
      ctx!.fillStyle = color;
      ctx!.fill();
    }

    function drawEdge(edge: LayoutEdge, colors: CanvasColors) {
      const { start, end, control } = edgeGeometry(edge);
      const stroke = bucketPalette(edge.from.isProcess ? edge.to : edge.from).border;

      ctx!.beginPath();
      ctx!.moveTo(start.x, start.y);
      ctx!.quadraticCurveTo(control.x, control.y, end.x, end.y);
      ctx!.strokeStyle = stroke;
      ctx!.globalAlpha = 0.7 * ((depthAlpha(edge.from, view) + depthAlpha(edge.to, view)) / 2);
      ctx!.lineWidth = 1.6 / Math.max(scale, 0.6);
      if (edge.dashed) ctx!.setLineDash([4, 3]);
      ctx!.stroke();
      ctx!.setLineDash([]);

      const tangent = tangentOnQuadratic(0.985, start, control, end);
      drawArrowhead(end.x, end.y, Math.atan2(tangent.y, tangent.x), 13 / Math.max(scale, 0.6), stroke);

      // Labels behind this point are unreadable and only add clutter.
      if (threeD && (edge.from.ds + edge.to.ds) / 2 < 0.88) {
        ctx!.globalAlpha = 1;
        return;
      }
      const at = pointOnQuadratic(0.5, start, control, end);
      drawEdgeLabel(edge.label, at.x, at.y, colors);
      ctx!.globalAlpha = 1;
    }

    function drawNodeBody(node: LayoutNode, colors: CanvasColors) {
      const palette = bucketPalette(node);
      const radius = nodeRadiusOf(node) * node.ds;
      ctx!.beginPath();
      ctx!.arc(node.px, node.py, radius, 0, Math.PI * 2);
      ctx!.fillStyle = palette.color;
      ctx!.fill();
      ctx!.strokeStyle = palette.border;
      ctx!.lineWidth = node.known ? 2 : 1.4;
      if (!node.known) ctx!.setLineDash([4, 3]);
      ctx!.stroke();
      ctx!.setLineDash([]);
      if (node.pinned) {
        // The focus reads as the anchor even before it is selected.
        ctx!.lineWidth = 1;
        ctx!.strokeStyle = colors.ink;
        ctx!.beginPath();
        ctx!.arc(node.px, node.py, radius + 5, 0, Math.PI * 2);
        ctx!.stroke();
      }
      if (selectedIdRef.current === node.id) {
        ctx!.strokeStyle = colors.ink;
        ctx!.lineWidth = 2.4;
        ctx!.beginPath();
        ctx!.arc(node.px, node.py, radius, 0, Math.PI * 2);
        ctx!.stroke();
      }
    }

    function drawNodeLabel(node: LayoutNode, colors: CanvasColors) {
      const depth = node.ds;
      if (threeD && depth < 0.88) return;
      const lines = nodeLabelLines(node);
      ctx!.font = `600 ${NODE_LABEL_FONT_SIZE * depth}px var(--font-body), system-ui, sans-serif`;
      ctx!.fillStyle = '#ffffff';
      ctx!.textAlign = 'center';
      ctx!.textBaseline = 'middle';
      const lineHeight = NODE_LABEL_LINE_HEIGHT * depth;
      let y = node.py - (lines.length * lineHeight) / 2 + lineHeight / 2;
      for (const line of lines) {
        ctx!.fillText(line, node.px, y);
        y += lineHeight;
      }
      // Caption: which bucket holds what for a satellite, and the clock for a
      // process — a ring of same-class processes is otherwise all one label.
      ctx!.font = `${9 * depth}px var(--font-body), system-ui, sans-serif`;
      ctx!.fillStyle = colors.muted;
      ctx!.fillText(node.caption, node.px, node.py + nodeRadiusOf(node) * depth + 11 * depth);
    }

    function draw() {
      const colors = readColors();
      const width = canvas!.clientWidth;
      const height = canvas!.clientHeight;
      ctx!.clearRect(0, 0, width, height);
      projectNodes(nodes, orbit.yaw, orbit.pitch, view);
      ctx!.save();
      ctx!.translate(width / 2 + pan.x, height / 2 + pan.y);
      ctx!.scale(scale, scale);

      const orderedEdges = threeD
        ? [...edges].sort((a, b) => (b.from.depth + b.to.depth) / 2 - (a.from.depth + a.to.depth) / 2)
        : edges;
      for (const edge of orderedEdges) drawEdge(edge, colors);

      if (threeD) {
        // Painter's algorithm, body and label together per node: drawing all
        // the bodies then all the labels would let a distant node's text land
        // on top of a near node that should be hiding it.
        const orderedNodes = [...nodes].sort((a, b) => b.depth - a.depth);
        for (const node of orderedNodes) {
          ctx!.globalAlpha = depthAlpha(node, view);
          drawNodeBody(node, colors);
          drawNodeLabel(node, colors);
        }
        ctx!.globalAlpha = 1;
      } else {
        for (const node of nodes) drawNodeBody(node, colors);
        for (const node of nodes) drawNodeLabel(node, colors);
      }
      ctx!.restore();
    }

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      canvas!.width = Math.max(1, Math.floor(container!.clientWidth * dpr));
      canvas!.height = Math.max(1, Math.floor(container!.clientHeight * dpr));
      canvas!.style.width = `${container!.clientWidth}px`;
      canvas!.style.height = `${container!.clientHeight}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }

    function screenToWorld(sx: number, sy: number) {
      return {
        x: (sx - canvas!.clientWidth / 2 - pan.x) / scale,
        y: (sy - canvas!.clientHeight / 2 - pan.y) / scale,
      };
    }

    function hit(point: { x: number; y: number }): LayoutNode | null {
      const ordered = [...nodes].sort((a, b) => a.depth - b.depth);
      for (const node of ordered) {
        if (Math.hypot(node.px - point.x, node.py - point.y) <= nodeRadiusOf(node) * node.ds + 4) {
          return node;
        }
      }
      return null;
    }

    function zoomAt(sx: number, sy: number, factor: number) {
      const before = screenToWorld(sx, sy);
      scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
      const after = screenToWorld(sx, sy);
      pan.x += (after.x - before.x) * scale;
      pan.y += (after.y - before.y) * scale;
      draw();
    }

    const onPointerDown = (ev: PointerEvent) => {
      const rect = canvas!.getBoundingClientRect();
      const world = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
      const node = hit(world);
      pressed = { node, x: ev.clientX, y: ev.clientY, moved: false };
      if (node) {
        setSelectedId(node.id);
        // Nodes cannot be dragged while orbiting: in 3D the plane is rotated.
        if (!threeD && !node.pinned) {
          dragging = node;
          dragOffset = { x: world.x - node.x, y: world.y - node.y };
        }
      } else if (threeD) {
        // Background drag orbits the camera rather than panning the plane.
        orbiting = { x: ev.clientX, y: ev.clientY, yaw: orbit.yaw, pitch: orbit.pitch };
      } else {
        panning = { x: ev.clientX - pan.x, y: ev.clientY - pan.y };
      }
      canvas!.setPointerCapture(ev.pointerId);
    };

    const onPointerMove = (ev: PointerEvent) => {
      if (pressed && Math.hypot(ev.clientX - pressed.x, ev.clientY - pressed.y) > 4) {
        pressed.moved = true;
      }
      if (orbiting) {
        orbit.yaw = orbiting.yaw + (ev.clientX - orbiting.x) * 0.008;
        orbit.pitch = Math.max(
          -Math.PI / 2.2,
          Math.min(Math.PI / 2.2, orbiting.pitch + (ev.clientY - orbiting.y) * 0.006),
        );
        draw();
      } else if (dragging) {
        const rect = canvas!.getBoundingClientRect();
        const world = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
        dragging.x = world.x - dragOffset.x;
        dragging.y = world.y - dragOffset.y;
        dragging.homeX = dragging.x;
        dragging.homeY = dragging.y;
        draw();
      } else if (panning) {
        pan.x = ev.clientX - panning.x;
        pan.y = ev.clientY - panning.y;
        draw();
      }
    };

    const onPointerUp = () => {
      orbiting = null;
      panning = null;
      dragging = null;
      pressed = null;
    };

    const onDoubleClick = (ev: MouseEvent) => {
      const rect = canvas!.getBoundingClientRect();
      const node = hit(screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top));
      // Double-clicking a process makes it the focus, as the cockpit's
      // inspector "focus" action does.
      if (node?.isProcess) pickRef.current(node.id);
    };

    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      const rect = canvas!.getBoundingClientRect();
      zoomAt(ev.clientX - rect.left, ev.clientY - rect.top, ev.deltaY < 0 ? 1.1 : 0.9);
    };

    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    canvas.addEventListener('dblclick', onDoubleClick);
    canvas.addEventListener('wheel', onWheel, { passive: false });

    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    let stopPhysics: (() => void) | null = null;
    if (params.physics) {
      stopPhysics = runPhysics(nodes, edges, params, { onTick: draw, onEnd: draw });
    } else {
      settlePhysicsSync(nodes, edges, params, { steps: 1 });
      draw();
    }

    apiRef.current = {
      draw,
      zoomBy: (factor) => zoomAt(canvas!.clientWidth / 2, canvas!.clientHeight / 2, factor),
      reset: () => {
        orbit.yaw = DEFAULT_YAW;
        orbit.pitch = DEFAULT_PITCH;
        pan.x = 0;
        pan.y = 0;
        scale = params.zoom;
        draw();
      },
    };

    return () => {
      stopPhysics?.();
      observer.disconnect();
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerUp);
      canvas.removeEventListener('dblclick', onDoubleClick);
      canvas.removeEventListener('wheel', onWheel);
      apiRef.current = null;
    };
  }, [layout, params]);

  const bucketCounts = useMemo(() => {
    const counts = new Map<BfoBucketType, number>();
    for (const node of layout.nodes) {
      if (!node.known || node.isProcess) continue;
      counts.set(node.bucket, (counts.get(node.bucket) ?? 0) + 1);
    }
    return counts;
  }, [layout]);

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      <canvas ref={canvasRef} className="block h-full w-full cursor-grab active:cursor-grabbing" />

      <EventGraphToolbar
        model={model}
        filters={filters}
        onFiltersChange={onFiltersChange}
        searchValue={searchValue}
        onSearchChange={onSearchChange}
        onPickProcess={onPickProcess}
        layout={String(params.toolbarLayout)}
      />

      {params.legend && (
        <div className="pointer-events-none absolute right-3 bottom-12 flex flex-col gap-1 rounded-lg border bg-background/90 p-2 text-[10px]">
          <strong className="text-[10px]">BFO buckets</strong>
          {(['Process', ...EVENT_GRAPH_BUCKETS] as BfoBucketType[]).map((bucket) => {
            const def = BFO_BUCKET_BY_TYPE[bucket];
            const count = bucket === 'Process' ? layout.nodes.filter((n) => n.isProcess).length : (bucketCounts.get(bucket) ?? 0);
            return (
              <span key={bucket} className={cnLegend(count)}>
                <i
                  className="inline-block h-2 w-2 rounded-sm"
                  style={{ background: count ? def?.color : 'transparent', border: `1px solid ${def?.border}` }}
                />
                {bucket}
                <span className="tabular-nums opacity-70">{count || UNKNOWN}</span>
              </span>
            );
          })}
        </div>
      )}

      <div className="absolute bottom-3 right-3 flex items-center gap-1">
        <span className="mr-2 text-[10px] text-muted-foreground">
          {params.view === '3d' ? 'drag to orbit' : 'drag to pan · drag a node to move it'} · double-click a
          process to focus · scroll to zoom
        </span>
        <button
          onClick={() => apiRef.current?.zoomBy(1.15)}
          className="rounded border bg-background/80 p-1.5 text-muted-foreground hover:text-foreground"
          aria-label="Zoom in"
          title="Zoom in"
        >
          <Plus size={13} />
        </button>
        <button
          onClick={() => apiRef.current?.zoomBy(0.87)}
          className="rounded border bg-background/80 p-1.5 text-muted-foreground hover:text-foreground"
          aria-label="Zoom out"
          title="Zoom out"
        >
          <Minus size={13} />
        </button>
        <button
          onClick={() => apiRef.current?.reset()}
          className="rounded border bg-background/80 p-1.5 text-muted-foreground hover:text-foreground"
          aria-label="Reset view"
          title="Reset view"
        >
          <RotateCcw size={13} />
        </button>
        <EventGraphParamsPanel
          params={params}
          onChange={onParamChange}
          onSwitchView={onSwitchView}
          onReset={onResetParams}
        />
      </div>

      {selectedNode && (
        <aside className="absolute right-3 top-3 max-h-[calc(100%-6rem)] w-64 overflow-y-auto rounded-lg border bg-background/95 p-3 text-xs shadow-sm">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Inspect</p>
          <p className="mt-1 flex items-center gap-1.5 font-medium">
            <span
              className="inline-block h-2 w-2 flex-shrink-0 rounded-full"
              style={{ backgroundColor: bucketPalette(selectedNode).color }}
            />
            <span className="break-words">{selectedNode.label}</span>
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {selectedNode.bucket}
            {!selectedNode.isProcess && selectedNode.processIds.length > 1 && (
              <> · shared by {selectedNode.processIds.length} processes</>
            )}
          </p>
          {selectedNode.fields.length === 0 ? (
            <p className="mt-3 text-[11px] text-muted-foreground">
              No payload field maps to this bucket. The event is stored as a flat
              <code className="mx-1 rounded bg-muted px-1">LogProcess</code>
              record, so this gap is an ontology gap, not a rendering one.
            </p>
          ) : (
            <dl className="mt-3 space-y-2">
              {selectedNode.fields.map((field) => (
                <div key={field.label}>
                  <dt className="font-mono text-[10px] text-muted-foreground">{field.label}</dt>
                  <dd className="break-all font-mono text-[11px]">{field.value}</dd>
                </div>
              ))}
            </dl>
          )}
          {selectedNode.isProcess && !selectedNode.pinned && (
            <button
              type="button"
              onClick={() => onPickProcess(selectedNode.id)}
              className="mt-3 w-full rounded border px-2 py-1 text-[11px] hover:bg-accent"
            >
              Focus this process
            </button>
          )}
        </aside>
      )}
    </div>
  );
}

function cnLegend(count: number): string {
  return `flex items-center gap-1.5 ${count ? 'text-foreground' : 'text-muted-foreground'}`;
}
