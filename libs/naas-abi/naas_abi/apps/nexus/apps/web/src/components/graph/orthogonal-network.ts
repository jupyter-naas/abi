import type { Edge, Network } from 'vis-network/standalone';
import { orthogonalRoute, parallelLanes, routeDistance, routeLabel, type Box, type Point } from './orthogonal-route';

export type RoutedEdge = { id: string; source: string; target: string; style: Edge };
type DrawnEdge = RoutedEdge & { points: Point[]; labelBox?: Box };
type State = { edges: RoutedEdge[]; selected: string[]; direction?: 'LR' | 'TD' };

/** Use public canvas events, so the existing network retains layout, focus and node inspection. */
export function installOrthogonalEdges(network: Network, container: HTMLElement, read: () => State) {
  let drawn: DrawnEdge[] = [], hovered: string | null = null, geometryKey = '';
  let previousEdges: RoutedEdge[] | undefined;
  let lanes = new Map<string, { lane: number; laneCount: number }>();
  const canvas = container.querySelector('canvas');
  const originalCursor = canvas?.style.cursor || '';

  function hitTest(point: Point) {
    const tolerance = 6 / Math.max(network.getScale(), 0.05);
    let nearest = tolerance, id: string | null = null;
    for (const edge of drawn) {
      const box = edge.labelBox;
      if (box && point.x >= box.left && point.x <= box.right && point.y >= box.top && point.y <= box.bottom) return edge.id;
      const distance = routeDistance(point, edge.points);
      if (distance <= nearest) { nearest = distance; id = edge.id; }
    }
    return id;
  }

  function draw(ctx: CanvasRenderingContext2D) {
    const { edges, selected, direction } = read();
    if (edges !== previousEdges) { lanes = parallelLanes(edges); previousEdges = edges; geometryKey = ''; }
    const positions = network.getPositions();
    const boxes = new Map<string, Box>();
    for (const [id, point] of Object.entries(positions)) {
      const box = network.getBoundingBox(id);
      // Bounding boxes are updated when nodes draw. Translate the previous size
      // to the current position so connections follow dragging in this same frame.
      const halfWidth = Math.max(1, (box.right - box.left) / 2), halfHeight = Math.max(1, (box.bottom - box.top) / 2);
      if (!Number.isFinite(halfWidth + halfHeight + point.x + point.y)) continue;
      boxes.set(id, { left: point.x - halfWidth, right: point.x + halfWidth, top: point.y - halfHeight, bottom: point.y + halfHeight });
    }
    const key = JSON.stringify([direction, [...boxes]]);
    if (key !== geometryKey) {
      geometryKey = key;
      drawn = edges.flatMap(edge => {
        const from = boxes.get(edge.source), to = boxes.get(edge.target);
        if (!from || !to) return [];
        const obstacles = [...boxes].filter(([id]) => id !== edge.source && id !== edge.target).map(([, box]) => box);
        return [{ ...edge, points: orthogonalRoute(from, to, { ...lanes.get(edge.id), loop: edge.source === edge.target, obstacles, direction }) }];
      });
    }
    const labelBackground = getComputedStyle(container).getPropertyValue('--background-hex').trim() || '#ffffff';
    const selectedIds = new Set(selected);
    const active = (edge: DrawnEdge) => selectedIds.has(edge.id) || hovered === edge.id;
    const ordered = [...drawn.filter(edge => !active(edge)), ...drawn.filter(active)];
    ctx.save();
    ctx.lineJoin = 'miter'; ctx.lineCap = 'butt'; ctx.shadowBlur = 0; ctx.shadowOffsetX = 0; ctx.shadowOffsetY = 0;
    for (const edge of ordered) {
      const style = edge.style, highlighted = active(edge);
      const colors = typeof style.color === 'object' ? style.color : { color: style.color || '#94a3b8' };
      const color = (highlighted ? colors.highlight : colors.color) || '#94a3b8';
      ctx.globalAlpha = highlighted ? 1 : colors.opacity ?? 1;
      ctx.strokeStyle = color; ctx.fillStyle = color;
      ctx.lineWidth = highlighted ? Math.max(2, Number(style.width || 1) + 1) : Number(style.width || 1);
      ctx.setLineDash(Array.isArray(style.dashes) ? style.dashes : style.dashes ? [5, 5] : []);
      ctx.beginPath();
      edge.points.forEach((point, index) => { if (index) ctx.lineTo(point.x, point.y); else ctx.moveTo(point.x, point.y); });
      ctx.stroke(); ctx.setLineDash([]);
      const arrow = typeof style.arrows === 'object' ? style.arrows.to : undefined;
      if (arrow === true || (typeof arrow === 'object' && arrow.enabled)) {
        const end = edge.points[edge.points.length - 1], previous = edge.points[edge.points.length - 2];
        const angle = Math.atan2(end.y - previous.y, end.x - previous.x);
        const size = Math.max(5, 12 * (typeof arrow === 'object' ? arrow.scaleFactor ?? 0.8 : 0.8));
        ctx.beginPath(); ctx.moveTo(end.x, end.y);
        ctx.lineTo(end.x - size * Math.cos(angle) + size * 0.4 * Math.sin(angle), end.y - size * Math.sin(angle) - size * 0.4 * Math.cos(angle));
        ctx.lineTo(end.x - size * Math.cos(angle) - size * 0.4 * Math.sin(angle), end.y - size * Math.sin(angle) + size * 0.4 * Math.cos(angle));
        ctx.closePath(); ctx.fill();
      }
    }
    // Draw labels last, at full opacity, to keep their text readable over crossing links.
    for (const edge of ordered) {
      edge.labelBox = undefined;
      if (!edge.style.label) continue;
      const font = typeof edge.style.font === 'object' ? edge.style.font : {};
      const size = font.size || 10, label = routeLabel(edge.points);
      ctx.globalAlpha = 1; ctx.font = `${size}px ${font.face || 'Inter, system-ui, sans-serif'}`;
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      const lines = edge.style.label.split('\n');
      const width = Math.max(...lines.map(line => ctx.measureText(line).width));
      const height = lines.length * (size + 3);
      const x = label.horizontal ? label.x - width / 2 : label.x + 6;
      const y = label.horizontal ? label.y - height / 2 - 4 : label.y;
      const box = { left: x - 3, right: x + width + 3, top: y - height / 2 - 2, bottom: y + height / 2 + 2 };
      edge.labelBox = box;
      ctx.fillStyle = font.background || labelBackground;
      ctx.fillRect(box.left, box.top, box.right - box.left, box.bottom - box.top);
      ctx.fillStyle = font.color || '#64748b';
      lines.forEach((line, i) => ctx.fillText(line, x, y + (i - (lines.length - 1) / 2) * (size + 3)));
    }
    ctx.restore();
  }

  function pointerMove(event: PointerEvent) {
    const rect = container.getBoundingClientRect();
    const point = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    const next = event.buttons || network.getNodeAt(point) ? null : hitTest(network.DOMtoCanvas(point));
    if (next === hovered) return;
    hovered = next;
    if (canvas) canvas.style.cursor = next ? 'pointer' : originalCursor;
    network.redraw();
  }
  function pointerLeave() {
    if (!hovered) return;
    hovered = null;
    if (canvas) canvas.style.cursor = originalCursor;
    network.redraw();
  }
  network.on('beforeDrawing', draw);
  container.addEventListener('pointermove', pointerMove);
  container.addEventListener('pointerleave', pointerLeave);
  network.redraw();
  return { hitTest, destroy() {
    network.off('beforeDrawing', draw);
    container.removeEventListener('pointermove', pointerMove);
    container.removeEventListener('pointerleave', pointerLeave);
    if (canvas) canvas.style.cursor = originalCursor;
    drawn = [];
  } };
}
