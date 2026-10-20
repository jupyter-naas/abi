/**
 * Where each connector's label goes, so that no two labels overlap, no label
 * covers a card, and as few as possible sit over another connector.
 *
 * Every label gets candidate positions along its own route: on a horizontal run
 * the label sits on the line, along it; beside a vertical run it sits left or
 * right of the line. Each candidate has a cost (what it covers, how far from the
 * middle of its run it is), and the choice of one candidate per label is the
 * assignment of least total cost, labels overlapping each other included. That
 * is a map-labelling problem (NP-hard in general), solved here as is usual:
 * greedily, the most constrained labels first, then by local search, moving one
 * label at a time to its best candidate given the others until none improves.
 *
 * Coordinates are canvas units.
 */
import type { Box, Point } from './orthogonal-route';

export type LabelRequest = { id: string; width: number; height: number; points: Point[] };
export type PlacedLabel = { x: number; y: number; box: Box };

const PAD = 2; // background around the text
const GAP = 4; // between a vertical run and a label beside it
const STEP = 8; // between two candidates along a run
const END = 6; // a label keeps this far from the ends of its run
const COVER_CARD = 100_000; // a label over a card is hidden behind it
const COVER_LABEL = 20_000; // two labels over each other cannot be read
const COVER_LINE = 300;
const OUTSIDE = 50_000; // a label outside the frame of the drawing is cut off when it is fitted to the view // a label over another connector hides where it goes
const OFF_MIDDLE = 0.5; // per unit from the middle of the run
const SHORT_RUN = 250; // a label on a run too short for it overhangs its ends
const BESIDE = 4; // a label beside a vertical run reads a little less well than one on a horizontal run
const MAX_ROUNDS = 8;

type Candidate = { box: Box; x: number; y: number; fixed: number };

export const boxesOverlap = (a: Box, b: Box) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

/** True when the run from ``a`` to ``b`` passes through ``box``. */
function crosses(a: Point, b: Point, box: Box) {
  if (Math.abs(a.x - b.x) < 1e-6) return a.x > box.left && a.x < box.right && Math.max(a.y, b.y) > box.top && Math.min(a.y, b.y) < box.bottom;
  return a.y > box.top && a.y < box.bottom && Math.max(a.x, b.x) > box.left && Math.min(a.x, b.x) < box.right;
}

/** Positions along each run of a route, each with what it costs on its own run. */
function candidatesFor(request: LabelRequest): { x: number; y: number; box: Box; own: number }[] {
  const { points } = request;
  const w = request.width + 2 * PAD, h = request.height + 2 * PAD;
  const out: { x: number; y: number; box: Box; own: number }[] = [];
  const at = (x: number, y: number, own: number) => out.push({ x, y, own, box: { left: x - w / 2, right: x + w / 2, top: y - h / 2, bottom: y + h / 2 } });
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1], b = points[i];
    const horizontal = Math.abs(a.y - b.y) < 1e-6;
    const lo = horizontal ? Math.min(a.x, b.x) : Math.min(a.y, b.y);
    const hi = horizontal ? Math.max(a.x, b.x) : Math.max(a.y, b.y);
    const size = horizontal ? w : h;
    const mid = (lo + hi) / 2;
    // The centres that keep the label within its run, or the middle of a run too short for it.
    const first = lo + END + size / 2, last = hi - END - size / 2;
    const centres: number[] = first > last ? [mid] : [mid];
    if (first <= last) {
      for (let d = STEP; mid - d >= first || mid + d <= last; d += STEP) {
        if (mid - d >= first) centres.push(mid - d);
        if (mid + d <= last) centres.push(mid + d);
      }
    }
    const short = first > last ? SHORT_RUN : 0;
    for (const c of centres) {
      const own = OFF_MIDDLE * Math.abs(c - mid) + short;
      if (horizontal) at(c, a.y, own);
      else {
        at(a.x + GAP + w / 2, c, own + BESIDE);
        at(a.x - GAP - w / 2, c, own + BESIDE);
      }
    }
  }
  return out;
}

/**
 * One position per label: ``requests`` are the labels with their routes,
 * ``cards`` the boxes labels must keep off, ``frame`` the box they must stay in.
 * Returns label centres and the boxes of the text.
 */
export function placeLabels(requests: LabelRequest[], cards: Box[], frame?: Box | null): Map<string, PlacedLabel> {
  const options = new Map<string, Candidate[]>();
  for (const request of requests) {
    if (request.points.length < 2) continue;
    const list = candidatesFor(request).map(({ box, x, y, own }) => {
      let fixed = own;
      for (const card of cards) if (boxesOverlap(box, card)) fixed += COVER_CARD;
      if (frame && (box.left < frame.left || box.right > frame.right || box.top < frame.top || box.bottom > frame.bottom)) fixed += OUTSIDE;
      for (const other of requests) {
        if (other.id === request.id) continue;
        for (let i = 1; i < other.points.length; i += 1) if (crosses(other.points[i - 1], other.points[i], box)) fixed += COVER_LINE;
      }
      return { box, x, y, fixed };
    });
    list.sort((p, q) => p.fixed - q.fixed);
    options.set(request.id, list);
  }
  const ids = [...options.keys()];
  const chosen = new Map<string, Candidate>();
  const costWith = (id: string, candidate: Candidate) => {
    let cost = candidate.fixed;
    for (const [other, pick] of chosen) if (other !== id && boxesOverlap(candidate.box, pick.box)) cost += COVER_LABEL;
    return cost;
  };
  const best = (id: string) => {
    let pick = options.get(id)![0], value = Infinity;
    for (const candidate of options.get(id)!) {
      if (candidate.fixed >= value) break; // sorted: none further can do better
      const cost = costWith(id, candidate);
      if (cost < value) { value = cost; pick = candidate; }
    }
    return pick;
  };
  // The most constrained first: those with the fewest clear places.
  const clear = (id: string) => options.get(id)!.filter(candidate => candidate.fixed < COVER_LINE).length;
  ids.sort((a, b) => clear(a) - clear(b) || a.localeCompare(b));
  for (const id of ids) chosen.set(id, best(id));
  for (let round = 0; round < MAX_ROUNDS; round += 1) {
    let moved = false;
    for (const id of ids) {
      const current = chosen.get(id)!;
      const next = best(id);
      if (next !== current && costWith(id, next) < costWith(id, current) - 1e-6) { chosen.set(id, next); moved = true; }
    }
    if (!moved) break;
  }
  const placed = new Map<string, PlacedLabel>();
  for (const [id, pick] of chosen) {
    placed.set(id, { x: pick.x, y: pick.y, box: { left: pick.box.left + PAD, right: pick.box.right - PAD, top: pick.box.top + PAD, bottom: pick.box.bottom - PAD } });
  }
  return placed;
}
