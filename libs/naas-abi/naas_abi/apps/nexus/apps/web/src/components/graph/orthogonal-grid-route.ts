/**
 * Square-corner routing of every connector together, on a grid of corridors,
 * for the BFO zone layout where the sides a connector uses are fixed by the
 * buckets it joins (bfo-edge-rules.ts).
 *
 *   - the corridors are the gaps between the cards, each cut into parallel
 *     tracks a few pixels apart, so many connectors can run side by side;
 *   - a connector is the shortest path along them, with a price for every bend,
 *     for crossing another connector, and a high one for sharing a track;
 *   - a connector leaves and enters a card by the sides it is given, or by any
 *     side when it is free. The connectors on one side of a card are spread
 *     along it in the order of where they are going, so they do not cross at it.
 *
 * Coordinates are canvas units. Ported from the people app
 * (naas_abi_marketplace intelligence/modules/people/apps/people/web/lib/orthogonal-route.js).
 */
import type { Side, SidesFor, EdgeSides } from './bfo-edge-rules';
import type { Box, Point } from './orthogonal-route';

export type GridEdge = { id: string; source: string; target: string };
/** The space the layout left outside the outermost cards, per side. */
export type Room = { top?: number; bottom?: number; left?: number; right?: number };
export type RouteFinding = { type: 'fallback' | 'bends'; edge: GridEdge; bends?: number };

const STUB = 14; // the least a connector runs straight out of a card
export const TRACK = 6; // the spacing between two parallel connectors
export const PORT_INSET = 10; // how far from a card's corner its first connector may attach
const CLEARANCE = 6; // how close a connector may pass to a card
const BEND = 22; // what a bend costs, in pixels of detour
const SHARE = 900; // what running on a track another connector uses costs
const CROSS = 150; // what crossing another connector costs: more than a short detour, less than a deep one
const MARGIN_TRACKS = 10; // tracks outside the outermost cards, at least
const MAX_TRACKS = 12; // tracks each side of the middle of one corridor
const ATTACH_LIMIT = 40; // corridor lines tried per port
const MAX_BENDS = 3;
// Many parallel tracks cost the same, and A* would expand every one of them:
// ties go to the state nearer the card, for routes within 0.1% of the cheapest.
const TIE = 1.001;
const WINDOW = 240;
const NEAR = 60;
const COARSE_FROM = 60; // cards from which a drawing is routed coarse first // how far from its first-pass route the second pass looks first // how far round its two cards a route is first looked for

const SIDES: Record<Side, Point> = { N: { x: 0, y: -1 }, S: { x: 0, y: 1 }, W: { x: -1, y: 0 }, E: { x: 1, y: 0 } };
const SIDE_NAMES = Object.keys(SIDES) as Side[];

const centre = (box: Box) => ({ x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2 });
const manhattan = (a: Point, b: Point) => Math.abs(b.x - a.x) + Math.abs(b.y - a.y);

/** Where a connector attaches on one side of a card; ``t`` is 0..1 along that side. */
function port(box: Box, side: Side, t: number): Point {
  const horizontalSide = side === 'N' || side === 'S';
  const length = horizontalSide ? box.right - box.left : box.bottom - box.top;
  const inset = Math.min(PORT_INSET, length / 4);
  const along = inset + t * (length - 2 * inset);
  if (side === 'N') return { x: box.left + along, y: box.top };
  if (side === 'S') return { x: box.left + along, y: box.bottom };
  if (side === 'W') return { x: box.left, y: box.top + along };
  return { x: box.right, y: box.top + along };
}

/** Drop repeated points and bends that go straight on. */
function simplify(points: Point[]): Point[] {
  const result: Point[] = [];
  for (const point of points) {
    if (result.length && manhattan(result[result.length - 1], point) < 1e-6) continue;
    while (result.length > 1) {
      const a = result[result.length - 2], b = result[result.length - 1];
      if ((Math.abs(a.x - b.x) < 1e-6 && Math.abs(b.x - point.x) < 1e-6 && (b.y - a.y) * (point.y - b.y) >= 0)
        || (Math.abs(a.y - b.y) < 1e-6 && Math.abs(b.y - point.y) < 1e-6 && (b.x - a.x) * (point.x - b.x) >= 0)) result.pop();
      else break;
    }
    result.push(point);
  }
  return result;
}

// ── the corridor grid ──

/** Merge overlapping [start, end] intervals; each keeps the items it covers. */
function mergeIntervals<T>(items: T[], start: (item: T) => number, end: (item: T) => number) {
  const sorted = [...items].sort((a, b) => start(a) - start(b));
  const merged: { start: number; end: number; items: T[] }[] = [];
  for (const item of sorted) {
    const last = merged[merged.length - 1];
    if (last && start(item) <= last.end) {
      last.end = Math.max(last.end, end(item));
      last.items.push(item);
    } else {
      merged.push({ start: start(item), end: end(item), items: [item] });
    }
  }
  return merged;
}

/** Track positions across a gap, centred, with room to spare at each side. */
function tracksIn(from: number, to: number, most = MAX_TRACKS) {
  const lines: number[] = [];
  const room = (to - from) / 2 - 1;
  if (room < 0) return lines;
  const mid = (from + to) / 2;
  for (let j = 0; Math.abs(j * TRACK) <= room && Math.abs(j) <= most; j = j > 0 ? -j : -j + 1) lines.push(mid + j * TRACK);
  return lines;
}

/**
 * The lines connectors run along. Cards are grouped into bands along ``along``
 * (rows, for a top-to-bottom layout); the gaps between bands are corridors across
 * the whole view, and the gaps between the cards of one band are corridors
 * across that band. Every corridor is cut into tracks.
 */
export function corridorLines(boxes: Box[], along: 'x' | 'y', room: Room = {}, { tracks = MAX_TRACKS, margin = MARGIN_TRACKS } = {}) {
  const rows = along === 'y';
  // Tracks outside the outermost cards: as many as the room the layout left holds.
  const tracksFor = (space?: number) => (margin < MARGIN_TRACKS ? margin : Math.max(margin, Math.floor((space ?? 0) / TRACK) - 1));
  const [before, after, low, high] = rows
    ? [tracksFor(room.top), tracksFor(room.bottom), tracksFor(room.left), tracksFor(room.right)]
    : [tracksFor(room.left), tracksFor(room.right), tracksFor(room.top), tracksFor(room.bottom)];
  const aStart = (b: Box) => (rows ? b.top : b.left) - CLEARANCE;
  const aEnd = (b: Box) => (rows ? b.bottom : b.right) + CLEARANCE;
  const cStart = (b: Box) => (rows ? b.left : b.top) - CLEARANCE;
  const cEnd = (b: Box) => (rows ? b.right : b.bottom) + CLEARANCE;

  const bands = mergeIntervals(boxes, aStart, aEnd);
  const alongLines = new Set<number>();
  const crossLines = new Set<number>();
  const keep = (set: Set<number>, value: number) => set.add(Math.round(value * 2) / 2);

  for (let i = 1; i < bands.length; i += 1) for (const v of tracksIn(bands[i - 1].end, bands[i].start, tracks)) keep(alongLines, v);
  for (let k = 0; k < before; k += 1) keep(alongLines, bands[0].start - 2 - k * TRACK);
  for (let k = 0; k < after; k += 1) keep(alongLines, bands[bands.length - 1].end + 2 + k * TRACK);
  const lowest = Math.min(...boxes.map(cStart));
  const highest = Math.max(...boxes.map(cEnd));
  for (let k = 0; k < low; k += 1) keep(crossLines, lowest - 2 - k * TRACK);
  for (let k = 0; k < high; k += 1) keep(crossLines, highest + 2 + k * TRACK);
  for (const band of bands) {
    const cells = mergeIntervals(band.items, cStart, cEnd);
    for (let i = 1; i < cells.length; i += 1) for (const v of tracksIn(cells[i - 1].end, cells[i].start, tracks)) keep(crossLines, v);
  }
  // Corridors are cut into tracks separately, so two lines can fall a pixel
  // apart, and connectors on them would be drawn as one. Keep a track between lines.
  const sorted = (set: Set<number>) => {
    const kept: number[] = [];
    for (const value of [...set].sort((x, y) => x - y)) {
      if (!kept.length || value - kept[kept.length - 1] >= TRACK - 0.5) kept.push(value);
    }
    return kept;
  };
  return rows ? { xs: sorted(crossLines), ys: sorted(alongLines) } : { xs: sorted(alongLines), ys: sorted(crossLines) };
}

/** A min-heap of (priority, value), in typed arrays: no allocation per entry. */
class Heap {
  private keys = new Float64Array(1024);
  private values = new Int32Array(1024);
  size = 0;
  clear() { this.size = 0; }
  push(priority: number, value: number) {
    if (this.size === this.keys.length) {
      const keys = new Float64Array(this.size * 2); keys.set(this.keys); this.keys = keys;
      const values = new Int32Array(this.size * 2); values.set(this.values); this.values = values;
    }
    const { keys, values } = this;
    let i = this.size++;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (keys[parent] <= priority) break;
      keys[i] = keys[parent]; values[i] = values[parent];
      i = parent;
    }
    keys[i] = priority; values[i] = value;
  }
  /** The least priority, read before ``pop``. */
  get topKey() { return this.keys[0]; }
  /** Remove the least entry; returns its value. */
  pop() {
    const { keys, values } = this;
    const value = values[0];
    const n = --this.size;
    if (n > 0) {
      const key = keys[n], last = values[n];
      let i = 0;
      for (;;) {
        const l = 2 * i + 1;
        if (l >= n) break;
        const m = l + 1 < n && keys[l + 1] < keys[l] ? l + 1 : l;
        if (keys[m] >= key) break;
        keys[i] = keys[m]; values[i] = values[m];
        i = m;
      }
      keys[i] = key; values[i] = last;
    }
    return value;
  }
}

/** Index of the last line at or below ``value`` (-1 when there is none). */
function lastAtOrBelow(lines: number[], value: number) {
  let lo = 0, hi = lines.length - 1, found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (lines[mid] <= value + 1e-6) { found = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return found;
}

/**
 * How far a connector reaches, for ordering. A U (both ends on the same side of
 * their cards) or a C spans along the side; anything else spans both ways. The
 * short ones are routed first, so they take the inner tracks of a nest and the
 * long ones the outer.
 */
function span(from: Box, to: Box, sides: EdgeSides) {
  const a = centre(from), b = centre(to);
  const source = sides?.source, target = sides?.target;
  if (source?.length === 1 && target?.length === 1 && source[0] === target[0]) {
    return source[0] === 'N' || source[0] === 'S' ? Math.abs(a.x - b.x) : Math.abs(a.y - b.y);
  }
  return manhattan(a, b);
}

/**
 * Two cards that face each other across a clear gap, overlapping along it: a
 * class and its subclass beside or below it in a zone. Their connector is one
 * straight run between the facing sides, when its sides are free or are those.
 * ``track`` is the position along the overlap; null when they do not face.
 */
function facing(from: Box, to: Box, sides: EdgeSides, cards: Box[]) {
  for (const horizontal of [true, false]) {
    const [aLo, aHi, bLo, bHi] = horizontal ? [from.top, from.bottom, to.top, to.bottom] : [from.left, from.right, to.left, to.right];
    const lo = Math.max(aLo, bLo) + PORT_INSET, hi = Math.min(aHi, bHi) - PORT_INSET;
    if (lo > hi) continue;
    const forward = horizontal ? to.left >= from.right : to.top >= from.bottom;
    const backward = horizontal ? from.left >= to.right : from.top >= to.bottom;
    if (!forward && !backward) continue;
    const out: Side = horizontal ? (forward ? 'E' : 'W') : (forward ? 'S' : 'N');
    const into: Side = horizontal ? (forward ? 'W' : 'E') : (forward ? 'N' : 'S');
    if (sides && !(sides.source.includes(out) && sides.target.includes(into))) continue;
    const [start, end] = horizontal ? (forward ? [from.right, to.left] : [from.left, to.right]) : (forward ? [from.bottom, to.top] : [from.top, to.bottom]);
    // Nothing may stand in the gap across the overlap.
    const blocked = cards.some(b => b !== from && b !== to && (horizontal
      ? b.right > Math.min(start, end) - CLEARANCE && b.left < Math.max(start, end) + CLEARANCE && b.bottom > lo - CLEARANCE && b.top < hi + CLEARANCE
      : b.bottom > Math.min(start, end) - CLEARANCE && b.top < Math.max(start, end) + CLEARANCE && b.right > lo - CLEARANCE && b.left < hi + CLEARANCE));
    if (blocked) continue;
    const at = (track: number) => (horizontal ? [{ x: start, y: track }, { x: end, y: track }] : [{ x: track, y: start }, { x: track, y: end }]);
    return { lo, hi, out, into, at };
  }
  return null;
}

type Attachment = { port: Point; point: Point; side: Side; states: { state: number; cost: number }[] };
type Found = { chain: number[]; points: Point[]; cost: number; startSide: Side; endSide: Side };
type Item = { edge: GridEdge; from: Box; to: Box; sides: EdgeSides; length: number };

/**
 * Route every connector.
 *
 * ``boxes`` maps a card id to its box. ``direction`` is "TD" or "LR" for the
 * tree layouts, whose corridors follow the tree's own axis. Returns a Map from
 * edge id to its points.
 *
 * ``sidesFor(edge)`` may fix the sides. A connector is routed on the sides it is
 * given; if there is no way through on them it is routed free, and that is
 * reported, not hidden. So is a connector with fixed sides that needs more than
 * three bends. ``room`` is the space the layout left outside the outermost cards.
 */
export function routeEdges(
  boxes: Map<string, Box>,
  edges: GridEdge[],
  options: { direction?: 'LR' | 'TD'; sidesFor?: SidesFor | null; room?: Room; report?: (finding: RouteFinding) => void; coarse?: boolean } = {},
): Map<string, Point[]> {
  const { direction, sidesFor, room, report, coarse } = options;
  const result = new Map<string, Point[]>();
  const cards = [...boxes.values()];
  const todo: Item[] = [];
  const straight: { edge: GridEdge; from: Box; to: Box; run: NonNullable<ReturnType<typeof facing>> }[] = [];
  for (const edge of edges) {
    const from = boxes.get(edge.source), to = boxes.get(edge.target);
    if (!from || !to) continue;
    if (edge.source === edge.target) {
      const a = centre(from);
      result.set(edge.id, [
        { x: from.right, y: a.y }, { x: from.right + 18, y: a.y }, { x: from.right + 18, y: from.top - 18 },
        { x: a.x, y: from.top - 18 }, { x: a.x, y: from.top },
      ]);
      continue;
    }
    const sides = sidesFor?.(edge) ?? null;
    const run = facing(from, to, sides, cards);
    if (run) straight.push({ edge, from, to, run });
    else todo.push({ edge, from, to, sides, length: span(from, to, sides) });
  }
  // Straight runs: in the middle of the overlap, a track apart when two cards share several.
  const pairs = new Map<string, typeof straight>();
  for (const item of straight) {
    const key = JSON.stringify([item.edge.source, item.edge.target].sort());
    pairs.set(key, [...(pairs.get(key) || []), item]);
  }
  for (const group of pairs.values()) {
    group.sort((a, b) => a.edge.id.localeCompare(b.edge.id));
    group.forEach((item, k) => {
      const mid = (item.run.lo + item.run.hi) / 2;
      const track = Math.max(item.run.lo, Math.min(item.run.hi, mid + (k - (group.length - 1) / 2) * TRACK));
      result.set(item.edge.id, item.run.at(track));
    });
  }
  if (!todo.length) return result;

  // A large drawing is routed twice: on a coarse grid, one line per corridor,
  // which settles the corridors each route takes; then on the fine grid of
  // tracks, each route looked for only along its coarse one.
  const guides = !coarse && cards.length >= COARSE_FROM ? routeEdges(boxes, edges, { ...options, coarse: true, report: undefined }) : null;
  const { xs, ys } = corridorLines(cards, direction === 'LR' ? 'x' : 'y', room, coarse ? { tracks: 0, margin: 3 } : {});
  const nx = xs.length, ny = ys.length;

  // What is free: a node is free outside every card, and so is the run between
  // two. Each card marks what it covers: the lines strictly inside it, found by
  // binary search, so the cost is the area the cards cover, not grid × cards.
  const nodeFree = new Uint8Array(nx * ny).fill(1);
  const hFree = new Uint8Array(Math.max(0, nx - 1) * ny).fill(1); // (i, j) to (i + 1, j)
  const vFree = new Uint8Array(nx * Math.max(0, ny - 1)).fill(1); // (i, j) to (i, j + 1)
  const firstAbove = (lines: number[], value: number) => lastAtOrBelow(lines, value) + 1; // first line > value (within 1e-6)
  const lastBelow = (lines: number[], value: number) => lastAtOrBelow(lines, value - 2e-6); // last line < value
  for (const b of cards) {
    const left = b.left - CLEARANCE, right = b.right + CLEARANCE, top = b.top - CLEARANCE, bottom = b.bottom + CLEARANCE;
    const i0 = firstAbove(xs, left), i1 = lastBelow(xs, right);
    const j0 = firstAbove(ys, top), j1 = lastBelow(ys, bottom);
    // Nodes inside, and the vertical runs on a line inside that reach into it.
    for (let j = j0; j <= j1; j += 1) for (let i = i0; i <= i1; i += 1) nodeFree[j * nx + i] = 0;
    for (let i = i0; i <= i1; i += 1) for (let j = Math.max(0, j0 - 1); j <= Math.min(ny - 2, j1); j += 1) vFree[i * (ny - 1) + j] = 0;
    // Horizontal runs on a line inside that reach into it.
    for (let j = j0; j <= j1; j += 1) for (let i = Math.max(0, i0 - 1); i <= Math.min(nx - 2, i1); i += 1) hFree[j * (nx - 1) + i] = 0;
  }

  // What is taken, by the connectors routed so far.
  let hUsed = new Uint8Array(0), vUsed = new Uint8Array(0), passH = new Uint8Array(0), passV = new Uint8Array(0);
  let drawnRuns: { vertical: boolean; at: number; lo: number; hi: number }[] = [];
  let spread = false; // once the ports are spread, no two stubs may share a line
  const reset = () => {
    drawnRuns = [];
    hUsed = new Uint8Array(hFree.length);
    vUsed = new Uint8Array(vFree.length);
    passH = new Uint8Array(nx * ny);
    passV = new Uint8Array(nx * ny);
    for (const item of straight) remember(result.get(item.edge.id)!);
  };

  /** Take every grid edge a drawn run lies along, even in part. */
  const markRun = (a: Point, b: Point) => {
    if (Math.abs(a.x - b.x) < 1e-6) {
      const i = lastAtOrBelow(xs, a.x);
      if (i < 0 || Math.abs(xs[i] - a.x) > 1e-6) return;
      const lo = Math.min(a.y, b.y), hi = Math.max(a.y, b.y);
      for (let j = 0; j < ny - 1; j += 1) if (Math.min(hi, ys[j + 1]) - Math.max(lo, ys[j]) > 1) vUsed[i * (ny - 1) + j] = 1;
    } else if (Math.abs(a.y - b.y) < 1e-6) {
      const j = lastAtOrBelow(ys, a.y);
      if (j < 0 || Math.abs(ys[j] - a.y) > 1e-6) return;
      const lo = Math.min(a.x, b.x), hi = Math.max(a.x, b.x);
      for (let i = 0; i < nx - 1; i += 1) if (Math.min(hi, xs[i + 1]) - Math.max(lo, xs[i]) > 1) hUsed[j * (nx - 1) + i] = 1;
    }
  };
  const remember = (points: Point[]) => {
    for (let i = 1; i < points.length; i += 1) markRun(points[i - 1], points[i]);
    for (let i = 1; i < points.length; i += 1) {
      const a = points[i - 1], b = points[i];
      const vertical = Math.abs(a.x - b.x) < 1e-6;
      drawnRuns.push(vertical
        ? { vertical, at: a.x, lo: Math.min(a.y, b.y), hi: Math.max(a.y, b.y) }
        : { vertical, at: a.y, lo: Math.min(a.x, b.x), hi: Math.max(a.x, b.x) });
    }
  };
  /** True when a stub from ``p`` to ``q`` would lie along a run already drawn. */
  const stubTaken = (p: Point, q: Point) => {
    const vertical = Math.abs(p.x - q.x) < 1e-6;
    const at = vertical ? p.x : p.y;
    const lo = vertical ? Math.min(p.y, q.y) : Math.min(p.x, q.x);
    const hi = vertical ? Math.max(p.y, q.y) : Math.max(p.x, q.x);
    return drawnRuns.some(run => run.vertical === vertical && Math.abs(run.at - at) < TRACK - 1 && Math.min(run.hi, hi) - Math.max(run.lo, lo) > 1);
  };

  // A run from a port out to a corridor line, and along it to the grid.
  const clearRun = (x0: number, y0: number, x1: number, y1: number, own: Box | null) =>
    !cards.some(b => b !== own && (x0 === x1
      ? x0 > b.left - CLEARANCE && x0 < b.right + CLEARANCE && Math.max(y0, y1) > b.top - CLEARANCE && Math.min(y0, y1) < b.bottom + CLEARANCE
      : y0 > b.top - CLEARANCE && y0 < b.bottom + CLEARANCE && Math.max(x0, x1) > b.left - CLEARANCE && Math.min(x0, x1) < b.right + CLEARANCE));

  /**
   * Where a port can join the grid: for each corridor line straight out from it,
   * the grid nodes beside the point where the port's line meets it. A state is
   * a node and the axis a path is on there.
   */
  function attachments(box: Box, side: Side, p: Point): Attachment[] {
    const d = SIDES[side];
    const out: Attachment[] = [];
    const stubIsVertical = d.y !== 0;
    const lines = stubIsVertical ? ys : xs;
    const across = stubIsVertical ? xs : ys;
    const start = stubIsVertical ? p.y : p.x;
    const dir = stubIsVertical ? d.y : d.x;
    const at = stubIsVertical ? p.x : p.y;
    // The nearest line at least a stub away, and on from there.
    let index = dir > 0 ? lastAtOrBelow(lines, start + STUB - 1e-6) + 1 : lastAtOrBelow(lines, start - STUB + 1e-6);
    let tried = 0;
    while (index >= 0 && index < lines.length && tried < ATTACH_LIMIT) {
      const line = lines[index];
      const reach = stubIsVertical ? clearRun(p.x, p.y, p.x, line, box) : clearRun(p.x, p.y, line, p.y, box);
      if (!reach) break;
      const point = stubIsVertical ? { x: p.x, y: line } : { x: line, y: p.y };
      // A stub along a run already drawn is allowed, at the price of sharing it.
      const shared = spread && stubTaken(p, point) ? SHARE : 0;
      tried += 1;
      const stub = Math.abs(line - start);
      const states: Attachment['states'] = [];
      const k = lastAtOrBelow(across, at);
      // The run from the port's line to the grid node lies along a grid edge, part
      // of it: if another connector has that edge, it is shared.
      const along = k >= 0 && k + 1 < across.length && (stubIsVertical ? hUsed[index * (nx - 1) + k] : vUsed[index * (ny - 1) + k]) ? SHARE : 0;
      const neighbours = new Set<number>();
      if (k >= 0) neighbours.add(k);
      if (k + 1 < across.length) neighbours.add(k + 1);
      for (const n of neighbours) {
        const node = stubIsVertical ? index * nx + n : n * nx + index;
        if (!nodeFree[node]) continue;
        const gap = Math.abs(across[n] - at);
        if (gap < 1e-6) {
          // The port lines up with the grid: the stub arrives along its own axis.
          states.push({ state: node * 2 + (stubIsVertical ? 1 : 0), cost: stub + shared });
          continue;
        }
        const clear = stubIsVertical ? clearRun(point.x, line, across[n], line, null) : clearRun(line, point.y, line, across[n], null);
        if (clear) states.push({ state: node * 2 + (stubIsVertical ? 0 : 1), cost: stub + gap + BEND + shared + along });
      }
      if (states.length) out.push({ port: p, point, side, states });
      index += dir > 0 ? 1 : -1;
    }
    return out;
  }

  const dist = new Float64Array(nx * ny * 2).fill(Infinity);
  const prev = new Int32Array(nx * ny * 2).fill(-1);
  const touched: number[] = [];
  const heap = new Heap();

  /**
   * The cheapest way between two sets of attachments, or null. ``target`` is the
   * card being reached; ``window`` the grid columns and rows the path may use.
   */
  function shortest(starts: Attachment[], ends: Attachment[], target: Box, window: { i0: number; i1: number; j0: number; j1: number }, mask?: Uint8Array): Found | null {
    // A*: a path to the card is never shorter than the Manhattan distance to it,
    // and it turns at least once when it must still change both column and row,
    // or the one it is not moving along.
    const heuristic = (state: number) => {
      const node = state >> 1, alongY = state & 1;
      const x = xs[node % nx], y = ys[(node / nx) | 0];
      const dx = Math.max(target.left - x, 0, x - target.right), dy = Math.max(target.top - y, 0, y - target.bottom);
      return dx + dy + ((dx > 0 && dy > 0) || (dx > 0 && alongY) || (dy > 0 && !alongY) ? BEND : 0);
    };
    // The buffers are shared by every search; ``touched`` lists what this one set.
    for (const s of touched) { dist[s] = Infinity; prev[s] = -1; }
    touched.length = 0;
    const seed = new Map<number, Attachment>();
    const goal = new Map<number, { cost: number; attach: Attachment }>();
    heap.clear();
    for (const attach of starts) {
      for (const { state, cost } of attach.states) {
        if (cost < dist[state]) {
          if (dist[state] === Infinity) touched.push(state);
          dist[state] = cost;
          seed.set(state, attach);
          heap.push(cost + TIE * heuristic(state), state);
        }
      }
    }
    for (const attach of ends) {
      for (const { state, cost } of attach.states) {
        if (!goal.has(state) || cost < goal.get(state)!.cost) goal.set(state, { cost, attach });
      }
    }
    let best = Infinity, bestState = -1;
    while (heap.size) {
      const f = heap.topKey, s = heap.pop();
      const d = dist[s];
      if (f > d + TIE * heuristic(s) + 1e-6) continue; // a stale entry
      if (f >= best) break;
      const reached = goal.get(s);
      if (reached && d + reached.cost < best) { best = d + reached.cost; bestState = s; }
      const node = s >> 1;
      const axis = s & 1; // 0: moving along x, 1: along y
      const i = node % nx, j = (node / nx) | 0;
      const relax = (next: number, cost: number) => {
        const ni = (next >> 1) % nx, nj = ((next >> 1) / nx) | 0;
        if (ni < window.i0 || ni > window.i1 || nj < window.j0 || nj > window.j1 || (mask && !mask[next >> 1])) return;
        if (cost < dist[next]) {
          if (dist[next] === Infinity) touched.push(next);
          dist[next] = cost;
          prev[next] = s;
          heap.push(cost + TIE * heuristic(next), next);
        }
      };
      if (axis === 0) {
        const through = CROSS * passV[node];
        if (i > 0 && hFree[j * (nx - 1) + i - 1]) relax((node - 1) * 2, d + xs[i] - xs[i - 1] + (hUsed[j * (nx - 1) + i - 1] ? SHARE : 0) + through);
        if (i < nx - 1 && hFree[j * (nx - 1) + i]) relax((node + 1) * 2, d + xs[i + 1] - xs[i] + (hUsed[j * (nx - 1) + i] ? SHARE : 0) + through);
      } else {
        const through = CROSS * passH[node];
        if (j > 0 && vFree[i * (ny - 1) + j - 1]) relax((node - nx) * 2 + 1, d + ys[j] - ys[j - 1] + (vUsed[i * (ny - 1) + j - 1] ? SHARE : 0) + through);
        if (j < ny - 1 && vFree[i * (ny - 1) + j]) relax((node + nx) * 2 + 1, d + ys[j + 1] - ys[j] + (vUsed[i * (ny - 1) + j] ? SHARE : 0) + through);
      }
      relax(node * 2 + (1 - axis), d + BEND);
    }
    if (bestState < 0) return null;
    // Walk back to the seed.
    const chain: number[] = [];
    for (let s = bestState; s >= 0; s = prev[s]) chain.push(s);
    chain.reverse();
    const nodes = chain.map(s => ({ x: xs[(s >> 1) % nx], y: ys[((s >> 1) / nx) | 0] }));
    const first = seed.get(chain[0])!;
    const last = goal.get(bestState)!.attach;
    return { chain, points: simplify([first.port, first.point, ...nodes, last.point, last.port]), cost: best, startSide: first.side, endSide: last.side };
  }

  /** Mark what a route takes, so the ones after it keep clear. */
  function occupy(chain: number[]) {
    const nodes: number[] = [];
    for (const state of chain) {
      const node = state >> 1;
      if (nodes[nodes.length - 1] !== node) nodes.push(node);
    }
    const col = (node: number) => node % nx;
    const row = (node: number) => (node / nx) | 0;
    // A node passed straight through is crossed by anything that turns across it.
    for (let n = 1; n < nodes.length - 1; n += 1) {
      const [a, b, c] = [nodes[n - 1], nodes[n], nodes[n + 1]];
      if (row(a) === row(b) && row(b) === row(c)) passH[b] = Math.min(255, passH[b] + 1);
      else if (col(a) === col(b) && col(b) === col(c)) passV[b] = Math.min(255, passV[b] + 1);
    }
  }

  // The short ones first: they have the fewest places to go.
  todo.sort((a, b) => a.length - b.length || a.edge.id.localeCompare(b.edge.id));

  /** The grid columns and rows that cover a box widened by ``by``. */
  const windowOf = (left: number, top: number, right: number, bottom: number, by: number) => ({
    i0: Math.max(0, lastAtOrBelow(xs, left - by)), i1: Math.min(nx - 1, lastAtOrBelow(xs, right + by) + 1),
    j0: Math.max(0, lastAtOrBelow(ys, top - by)), j1: Math.min(ny - 1, lastAtOrBelow(ys, bottom + by) + 1),
  });
  const everywhere = { i0: 0, i1: nx - 1, j0: 0, j1: ny - 1 };
  const band = new Uint8Array(nx * ny);
  const banded: number[] = [];
  /**
   * The route between the given sides. It is looked for first near ``near``
   * (the route the first pass found, coarse to fine), then in a window round the
   * two cards, which is where nearly every route lies, and only then everywhere.
   */
  const bothEnds = (item: Item, sidesA: Side[], sidesB: Side[], slotA: number, slotB: number, near?: Point[]) => {
    const starts = sidesA.flatMap(side => attachments(item.from, side, port(item.from, side, slotA)));
    const ends = sidesB.flatMap(side => attachments(item.to, side, port(item.to, side, slotB)));
    const { from, to } = item;
    const around = { left: Math.min(from.left, to.left), top: Math.min(from.top, to.top), right: Math.max(from.right, to.right), bottom: Math.max(from.bottom, to.bottom) };
    if (near && near.length > 1) {
      // A band ``NEAR`` wide round each run of the guide.
      for (const node of banded) band[node] = 0;
      banded.length = 0;
      for (let k = 1; k < near.length; k += 1) {
        const w = windowOf(Math.min(near[k - 1].x, near[k].x), Math.min(near[k - 1].y, near[k].y), Math.max(near[k - 1].x, near[k].x), Math.max(near[k - 1].y, near[k].y), NEAR);
        for (let j = w.j0; j <= w.j1; j += 1) for (let i = w.i0; i <= w.i1; i += 1) { const node = j * nx + i; if (!band[node]) { band[node] = 1; banded.push(node); } }
      }
      const found = shortest(starts, ends, to, everywhere, band);
      if (found) return found;
    }
    const reach = WINDOW + Math.abs(centre(from).x - centre(to).x) / 4 + Math.abs(centre(from).y - centre(to).y) / 4;
    return shortest(starts, ends, to, windowOf(around.left, around.top, around.right, around.bottom, reach)) ?? shortest(starts, ends, to, everywhere);
  };

  // Pass 1: which side of each card, with every port in the middle of its side.
  reset();
  spread = false;
  const chosen = new Map<string, Found>();
  const fallen = new Set<string>();
  for (const item of todo) {
    let found = bothEnds(item, item.sides?.source ?? SIDE_NAMES, item.sides?.target ?? SIDE_NAMES, 0.5, 0.5, guides?.get(item.edge.id));
    if (!found && item.sides) {
      // No way through on the sides the rule gives: free choice, and say so.
      found = bothEnds(item, SIDE_NAMES, SIDE_NAMES, 0.5, 0.5);
      fallen.add(item.edge.id);
      report?.({ type: 'fallback', edge: item.edge });
    }
    if (!found) continue;
    chosen.set(item.edge.id, found);
    occupy(found.chain);
    remember(found.points);
  }

  // Ports: on each side of a card, in the order of where the connectors go next.
  // ``fixed``: where along the side a straight run already attaches (0..1, as a slot).
  const ends = new Map<string, { edgeId: string; which: 'a' | 'b'; far: number; own: number; fixed?: number }[]>();
  const attach = (cardId: string, side: Side, edgeId: string, which: 'a' | 'b', far: number, own: number, fixed?: number) => {
    const key = `${cardId}|${side}`;
    if (!ends.has(key)) ends.set(key, []);
    ends.get(key)!.push({ edgeId, which, far, own, fixed });
  };
  const slotAt = (box: Box, side: Side, point: Point) => {
    const horizontalSide = side === 'N' || side === 'S';
    const length = horizontalSide ? box.right - box.left : box.bottom - box.top;
    const inset = Math.min(PORT_INSET, length / 4);
    const along = horizontalSide ? point.x - box.left : point.y - box.top;
    return length > 2 * inset ? (along - inset) / (length - 2 * inset) : 0.5;
  };
  for (const item of straight) {
    const [a, b] = result.get(item.edge.id)!;
    attach(item.edge.source, item.run.out, item.edge.id, 'a', 0, 0, slotAt(item.from, item.run.out, a));
    attach(item.edge.target, item.run.into, item.edge.id, 'b', 0, 0, slotAt(item.to, item.run.into, b));
  }
  // Where a route first leaves the line its port is on, along that side.
  const heads = (list: Point[], side: Side) => {
    const key = (p: Point) => (side === 'N' || side === 'S' ? p.x : p.y);
    const other = list.find(p => Math.abs(key(p) - key(list[0])) > 0.5);
    return key(other || list[0]);
  };
  for (const item of todo) {
    const pick = chosen.get(item.edge.id);
    if (!pick) continue;
    const along = (box: Box, side: Side) => (side === 'N' || side === 'S' ? centre(box).x : centre(box).y);
    attach(item.edge.source, pick.startSide, item.edge.id, 'a', heads(pick.points, pick.startSide), along(item.from, pick.startSide));
    attach(item.edge.target, pick.endSide, item.edge.id, 'b', heads([...pick.points].reverse(), pick.endSide), along(item.to, pick.endSide));
  }
  const slot = new Map<string, number>();
  for (const list of ends.values()) {
    // Those heading one way, then those going straight, then the other way; and
    // within each way the longest first from the middle out, so that a U or a C
    // nests inside the next one and their legs do not cross at the card.
    const group = (entry: { far: number; own: number }) => (entry.far < entry.own - 0.5 ? 0 : entry.far > entry.own + 0.5 ? 2 : 1);
    const free = list.filter(entry => entry.fixed === undefined);
    free.sort((p, q) => group(p) - group(q) || q.far - p.far || p.edgeId.localeCompare(q.edgeId));
    // A straight run keeps its place: the others take the slots furthest from it.
    const slots = list.map((_, i) => (i + 1) / (list.length + 1));
    for (const entry of list) {
      if (entry.fixed === undefined) continue;
      const nearest = slots.reduce((best, value, i) => (Math.abs(value - entry.fixed!) < Math.abs(slots[best] - entry.fixed!) ? i : best), 0);
      slots.splice(nearest, 1);
    }
    free.forEach((entry, i) => slot.set(`${entry.edgeId}|${entry.which}`, slots[i]));
  }

  // Pass 2: with the ports fixed, the tracks.
  reset();
  spread = true;
  for (const item of todo) {
    const pick = chosen.get(item.edge.id);
    const slotOf = (which: 'a' | 'b') => slot.get(`${item.edge.id}|${which}`) ?? 0.5;
    let found = pick ? bothEnds(item, [pick.startSide], [pick.endSide], slotOf('a'), slotOf('b'), pick.points) : null;
    // The spread ports left no way through: keep the required sides if they can be kept.
    if (!found && item.sides && !fallen.has(item.edge.id)) found = bothEnds(item, item.sides.source, item.sides.target, 0.5, 0.5);
    // Still none: let the sides change.
    if (!found) found = bothEnds(item, SIDE_NAMES, SIDE_NAMES, 0.5, 0.5);
    let points: Point[];
    if (found) {
      points = found.points;
      occupy(found.chain);
      remember(found.points);
    } else {
      // Nothing is clear: a plain elbow, drawn anyway rather than not at all.
      points = simplify([centre(item.from), { x: centre(item.to).x, y: centre(item.from).y }, centre(item.to)]);
    }
    result.set(item.edge.id, points);
    const bends = points.length - 2;
    if (item.sides && bends > MAX_BENDS) report?.({ type: 'bends', edge: item.edge, bends });
  }
  straighten(result, todo, cards);
  return result;
}

/**
 * Routes with two bends or more replaced, where it is clear, by one with a single
 * bend: out of one card along its row (or column) to the other's column (or
 * row), and into it. The sides must be ones the rule allows; the new route must
 * keep off every card, not run along another route, and not attach where
 * another already does.
 */
function straighten(result: Map<string, Point[]>, items: Item[], cards: Box[]) {
  const runs = (points: Point[]) => points.slice(1).map((b, k) => [points[k], b] as const);
  const sideOf = (box: Box, p: Point): Side => (Math.abs(p.y - box.top) < 1e-6 ? 'N' : Math.abs(p.y - box.bottom) < 1e-6 ? 'S' : Math.abs(p.x - box.left) < 1e-6 ? 'W' : 'E');
  const clearOfCards = (a: Point, b: Point, own: Box[]) => !cards.some(box => !own.includes(box) && (Math.abs(a.x - b.x) < 1e-6
    ? a.x > box.left - CLEARANCE && a.x < box.right + CLEARANCE && Math.max(a.y, b.y) > box.top - CLEARANCE && Math.min(a.y, b.y) < box.bottom + CLEARANCE
    : a.y > box.top - CLEARANCE && a.y < box.bottom + CLEARANCE && Math.max(a.x, b.x) > box.left - CLEARANCE && Math.min(a.x, b.x) < box.right + CLEARANCE));
  // Inside its own cards, a run is only the stub from the border.
  const alongOther = (a: Point, b: Point, id: string) => {
    const vertical = Math.abs(a.x - b.x) < 1e-6;
    const at = vertical ? a.x : a.y, lo = vertical ? Math.min(a.y, b.y) : Math.min(a.x, b.x), hi = vertical ? Math.max(a.y, b.y) : Math.max(a.x, b.x);
    for (const [other, points] of result) {
      if (other === id) continue;
      for (const [c, d] of runs(points)) {
        if ((Math.abs(c.x - d.x) < 1e-6) !== vertical) continue;
        const oat = vertical ? c.x : c.y, olo = vertical ? Math.min(c.y, d.y) : Math.min(c.x, d.x), ohi = vertical ? Math.max(c.y, d.y) : Math.max(c.x, d.x);
        if (Math.abs(oat - at) < TRACK && Math.min(hi, ohi) - Math.max(lo, olo) > 1) return true;
      }
    }
    return false;
  };
  const portTaken = (p: Point, id: string) => [...result].some(([other, points]) => other !== id
    && [points[0], points[points.length - 1]].some(q => Math.abs(q.x - p.x) + Math.abs(q.y - p.y) < TRACK));
  for (const item of items) {
    const points = result.get(item.edge.id);
    if (!points || points.length < 4) continue;
    const { from, to, sides } = item;
    const a = centre(from), b = centre(to);
    const options: Point[][] = [];
    // Along the source's row, then down (or up) the target's column.
    {
      const exitX = b.x > a.x ? from.right : from.left, entryY = b.y > a.y ? to.top : to.bottom;
      if ((b.x > from.right || b.x < from.left) && (a.y < to.top || a.y > to.bottom)) options.push([{ x: exitX, y: a.y }, { x: b.x, y: a.y }, { x: b.x, y: entryY }]);
      const exitY = b.y > a.y ? from.bottom : from.top, entryX = b.x > a.x ? to.left : to.right;
      if ((b.y > from.bottom || b.y < from.top) && (a.x < to.left || a.x > to.right)) options.push([{ x: a.x, y: exitY }, { x: a.x, y: b.y }, { x: entryX, y: b.y }]);
    }
    for (const route of options) {
      const out = sideOf(from, route[0]), into = sideOf(to, route[route.length - 1]);
      if (sides && !(sides.source.includes(out) && sides.target.includes(into))) continue;
      if (portTaken(route[0], item.edge.id) || portTaken(route[route.length - 1], item.edge.id)) continue;
      if (runs(route).some(([p, q]) => !clearOfCards(p, q, [from, to]) || alongOther(p, q, item.edge.id))) continue;
      // The corner must be outside both cards, past a stub.
      const corner = route[1];
      if (Math.abs(corner.x - route[0].x) + Math.abs(corner.y - route[0].y) < STUB || Math.abs(corner.x - route[2].x) + Math.abs(corner.y - route[2].y) < STUB) continue;
      result.set(item.edge.id, route);
      break;
    }
  }
}
