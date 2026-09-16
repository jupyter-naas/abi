import { architecture } from './architecture-model';
export type Dependency = (typeof architecture.edges)[number];
export function describeDependency(edge: Dependency) {
  const label = (id: string) => architecture.components.find(c => c.id === id)?.label ?? id;
  return { title: `${label(edge.source)} → ${label(edge.target)}`, detail: Object.entries(edge.relations).map(([name, count]) => `${name.replaceAll('_', ' ')}: ${count}`).join(' · ') };
}
export function segmentDistance(px: number, py: number, ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax, dy = by - ay;
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy || 1)));
  return Math.hypot(px - ax - t * dx, py - ay - t * dy);
}
// Read the diagram from infrastructure foundations to user-facing applications.
export const DIAGRAM_LAYERS = [...architecture.layers].reverse();
export const GRAPH_COLUMN = 320;
export const GRAPH_ROW = 68;
export const GRAPH_NODE_WIDTH = 220;
export const GRAPH_NODE_HEIGHT = 48;
/** Fixed architectural lanes: positions never depend on the number of links. */
export function graphPositions() {
  return DIAGRAM_LAYERS.flatMap((layer, column) =>
    architecture.components.filter(c => c.layer === layer.id)
      .sort((a, b) => a.label.localeCompare(b.label))
      .map((c, row) => ({ id: c.id, x: column * GRAPH_COLUMN, y: row * GRAPH_ROW, column, row })));
}
export function graphRoute(a: { x: number; y: number }, b: { x: number; y: number }) {
  const direction = b.x >= a.x ? 1 : -1;
  const start = { x: a.x + direction * GRAPH_NODE_WIDTH / 2, y: a.y };
  const end = { x: b.x - direction * GRAPH_NODE_WIDTH / 2, y: b.y };
  if (a.x === b.x) {
    end.x = b.x + GRAPH_NODE_WIDTH / 2;
    return [start, { x: start.x + 24, y: start.y }, { x: start.x + 24, y: end.y }, end];
  }
  // Horizontal runs occupy row gaps; vertical runs stay in column gutters.
  const sx = start.x + direction * 20, tx = end.x - direction * 20;
  const corridor = a.y + GRAPH_ROW / 2;
  return [start, { x: sx, y: a.y }, { x: sx, y: corridor }, { x: tx, y: corridor }, { x: tx, y: b.y }, end];
}
