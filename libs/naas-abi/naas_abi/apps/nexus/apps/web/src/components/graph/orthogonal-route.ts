/** Square-corner routing shared by drawing and hit testing. Coordinates are canvas units. */
export type Point = { x: number; y: number };
export type Box = { left: number; top: number; right: number; bottom: number };
export type RouteOptions = { lane?: number; laneCount?: number; loop?: boolean; obstacles?: Box[]; direction?: 'LR' | 'TD' };
const GAP = 18;
const centre = (a: Box) => ({ x: (a.left + a.right) / 2, y: (a.top + a.bottom) / 2 });
const distance = (a: Point, b: Point) => Math.abs(b.x - a.x) + Math.abs(b.y - a.y);
const transpose = (a: Box): Box => ({ left: a.top, right: a.bottom, top: a.left, bottom: a.right });

function simplify(points: Point[]): Point[] {
  const result: Point[] = [];
  for (const point of points) {
    if (result.length && distance(result[result.length - 1], point) === 0) continue;
    while (result.length > 1) {
      const a = result[result.length - 2], b = result[result.length - 1];
      // Remove redundant bends, but retain U-turns around overlapping nodes.
      if ((a.x === b.x && b.x === point.x && (b.y - a.y) * (point.y - b.y) >= 0)
        || (a.y === b.y && b.y === point.y && (b.x - a.x) * (point.x - b.x) >= 0)) result.pop();
      else break;
    }
    result.push(point);
  }
  return result;
}

export function crossesBox(a: Point, b: Point, box: Box): boolean {
  if (a.x === b.x) return a.x > box.left && a.x < box.right && Math.max(a.y, b.y) > box.top && Math.min(a.y, b.y) < box.bottom;
  return a.y > box.top && a.y < box.bottom && Math.max(a.x, b.x) > box.left && Math.min(a.x, b.x) < box.right;
}

/** Try facing ports, then outside corridors, as in the infrastructure diagram. */
function horizontalRoutes(a: Box, b: Box, lane: number, laneCount: number, obstacles: Box[]): Point[][] {
  const ca = centre(a), cb = centre(b), sign = cb.x >= ca.x ? 1 : -1;
  const offset = (box: Box) => lane * Math.min(10, Math.max(0, box.bottom - box.top - 10) / Math.max(1, laneCount - 1));
  const start = { x: sign > 0 ? a.right : a.left, y: ca.y + offset(a) };
  const end = { x: sign > 0 ? b.left : b.right, y: cb.y + offset(b) };
  const gap = sign * (end.x - start.x);
  const candidates: Point[][] = [];
  if (gap >= GAP * 2) {
    const sx = start.x + sign * GAP, tx = end.x - sign * GAP;
    const mid = Math.max(Math.min(sx, tx), Math.min(Math.max(sx, tx), (sx + tx) / 2 + lane * 14));
    const rails = new Set([mid, sx, tx]);
    for (const o of obstacles) for (const x of [o.left - GAP, o.right + GAP]) if (x >= Math.min(sx, tx) && x <= Math.max(sx, tx)) rails.add(x);
    for (const x of rails) candidates.push([start, { x, y: start.y }, { x, y: end.y }, end]);
    const corridors = new Set([Math.min(a.top, b.top) - GAP - Math.abs(lane) * 14, Math.max(a.bottom, b.bottom) + GAP + Math.abs(lane) * 14]);
    for (const o of obstacles) { corridors.add(o.top - GAP); corridors.add(o.bottom + GAP); }
    for (const y of corridors) candidates.push([start, { x: sx, y: start.y }, { x: sx, y }, { x: tx, y }, { x: tx, y: end.y }, end]);
  }
  // Stacked/overlapping columns: exit and enter on the same outside face.
  for (const side of [-1, 1]) {
    const x = side > 0 ? Math.max(a.right, b.right) + GAP + Math.abs(lane) * 14 : Math.min(a.left, b.left) - GAP - Math.abs(lane) * 14;
    const s = { x: side > 0 ? a.right : a.left, y: start.y };
    const e = { x: side > 0 ? b.right : b.left, y: end.y };
    if (s.y !== e.y) candidates.push([s, { x, y: s.y }, { x, y: e.y }, e]);
  }
  return candidates;
}

export function orthogonalRoute(from: Box, to: Box, options: RouteOptions = {}): Point[] {
  const { lane = 0, laneCount = 1, direction, loop = false } = options;
  const margin = GAP * 2 + Math.abs(lane) * 14;
  const obstacles = (options.obstacles || []).filter(box => box.right >= Math.min(from.left, to.left) - margin && box.left <= Math.max(from.right, to.right) + margin && box.bottom >= Math.min(from.top, to.top) - margin && box.top <= Math.max(from.bottom, to.bottom) + margin);
  if (loop || (centre(from).x === centre(to).x && centre(from).y === centre(to).y)) {
    const gap = GAP + (lane + (laneCount - 1) / 2) * 14;
    const a = centre(from), b = centre(to);
    return [{ x: from.right, y: a.y }, { x: Math.max(from.right, to.right) + gap, y: a.y },
      { x: Math.max(from.right, to.right) + gap, y: Math.min(from.top, to.top) - gap },
      { x: b.x, y: Math.min(from.top, to.top) - gap }, { x: b.x, y: to.top }];
  }
  const a = centre(from), b = centre(to);
  const verticalFirst = direction ? direction === 'TD' : Math.abs(b.y - a.y) > Math.abs(b.x - a.x);
  const horizontal = horizontalRoutes(from, to, lane, laneCount, obstacles);
  const vertical = horizontalRoutes(transpose(from), transpose(to), lane, laneCount, obstacles.map(transpose)).map(route => route.map(p => ({ x: p.y, y: p.x })));
  const candidates = (verticalFirst ? [...vertical, ...horizontal] : [...horizontal, ...vertical]).map(simplify);
  const blockers = [from, to, ...obstacles];
  function cost(route: Point[]) {
    let value = route.length * 12;
    for (let i = 1; i < route.length; i++) {
      value += distance(route[i - 1], route[i]);
      for (const box of blockers) if (crossesBox(route[i - 1], route[i], box)) value += 1_000_000;
    }
    return value;
  }
  // Stable order breaks ties, keeping the preferred orientation and parallel lanes.
  let best = candidates[0], bestCost = cost(best);
  for (const route of candidates.slice(1)) { const value = cost(route); if (value < bestCost) { best = route; bestCost = value; } }
  return best;
}

export function routeDistance(point: Point, route: Point[]): number {
  let nearest = Infinity;
  for (let i = 1; i < route.length; i++) {
    const a = route[i - 1], b = route[i];
    const x = Math.max(Math.min(a.x, b.x), Math.min(Math.max(a.x, b.x), point.x));
    const y = Math.max(Math.min(a.y, b.y), Math.min(Math.max(a.y, b.y), point.y));
    nearest = Math.min(nearest, Math.hypot(point.x - x, point.y - y));
  }
  return nearest;
}

/** Keep labels horizontal, beside the longest run instead of at a bend. */
export function routeLabel(route: Point[]) {
  let index = 1;
  for (let i = 2; i < route.length; i++) if (distance(route[i - 1], route[i]) > distance(route[index - 1], route[index])) index = i;
  const a = route[index - 1], b = route[index];
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, horizontal: a.y === b.y };
}

export function parallelLanes(edges: { id: string; source: string; target: string }[]) {
  const groups = new Map<string, string[]>();
  for (const edge of edges) {
    const key = JSON.stringify([edge.source, edge.target].sort());
    const ids = groups.get(key) || []; ids.push(edge.id); groups.set(key, ids);
  }
  const result = new Map<string, { lane: number; laneCount: number }>();
  for (const ids of groups.values()) ids.sort().forEach((id, i) => result.set(id, { lane: i - (ids.length - 1) / 2, laneCount: ids.length }));
  return result;
}
