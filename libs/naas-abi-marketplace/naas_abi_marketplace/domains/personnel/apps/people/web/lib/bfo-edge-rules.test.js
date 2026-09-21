/**
 * The side rules of the BFO zone layout: a connector's sides are fixed by the
 * buckets it joins. Run with ``node --test web/lib/`` from apps/people.
 *
 * These build real cards for the seven buckets, lay them out with bucketLayout
 * and route with routeEdges, so they check the layout and the router as well as
 * the table: a rule that the layout leaves no room for fails here.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { BFO_EDGE_RULES, edgeSides, sideLoads, sidesFor } from "./bfo-edge-rules.js";
import { bucketLayout, cardSize, wrapLabel } from "./network-layout.js";
import { routeEdges } from "./orthogonal-route.js";

const BUCKETS = ["Process", "Temporal Region", "Material Entity", "Site", "GDC", "Quality", "Realizable"];

/** Two cards for each bucket, laid out as the page lays them out. */
function arrange(edgesOf) {
  const cards = BUCKETS.flatMap((bucket) => [1, 2].map((n) => ({ id: `${bucket} ${n}`, label: `${bucket} ${n}`, bucket })));
  const bucketOf = new Map(cards.map((card) => [card.id, card.bucket]));
  const edges = edgesOf(cards).map((edge, i) => ({ id: `e${i}`, ...edge }));
  const sidesOf = edgeSides((id) => bucketOf.get(id));
  const loads = sideLoads(edges, sidesOf);
  const sized = cards.map((card) => {
    const { width, height } = cardSize(wrapLabel(card.label), loads.get(card.id));
    return { ...card, width, height, bucketLabel: card.bucket };
  });
  const layout = bucketLayout(sized, edges, { aspect: 1.8, sidesFor: sidesOf });
  const boxes = new Map(
    sized.map((card) => {
      const at = layout.positions.get(card.id);
      return [card.id, { left: at.x - card.width / 2, right: at.x + card.width / 2, top: at.y - card.height / 2, bottom: at.y + card.height / 2 }];
    }),
  );
  return { cards: sized, edges, boxes, layout, sidesOf };
}

/** Which border of ``box`` a point is on, and that it is not in a corner. */
function borderOf(point, box) {
  const near = (a, b) => Math.abs(a - b) < 1e-6;
  const within = (v, lo, hi) => v > lo + 1 && v < hi - 1; // never in a corner
  const sides = [];
  if (near(point.y, box.top) && within(point.x, box.left, box.right)) sides.push("N");
  if (near(point.y, box.bottom) && within(point.x, box.left, box.right)) sides.push("S");
  if (near(point.x, box.left) && within(point.y, box.top, box.bottom)) sides.push("W");
  if (near(point.x, box.right) && within(point.y, box.top, box.bottom)) sides.push("E");
  assert.equal(sides.length, 1, `point (${point.x}, ${point.y}) is on ${sides.length} borders of the card`);
  return sides[0];
}

/**
 * The card an end of a rule uses. Each bucket has two: the layout puts the one
 * that connectors leave by the south (or the east) last in its zone, and the one
 * they enter by the west first, which is what the rule needs to reach it.
 */
const cardFor = (bucket, side) => `${bucket} ${(side === "W" && bucket !== "Process") || (side === "E" && bucket === "Process") ? 2 : 1}`;

/** True when two connectors run along the same track for more than a pixel. */
function shareATrack(a, b) {
  const runs = (points) => points.slice(1).map((p, i) => ({ from: points[i], to: p }));
  for (const r of runs(a)) {
    for (const s of runs(b)) {
      const vertical = Math.abs(r.from.x - r.to.x) < 1e-6;
      if (vertical !== Math.abs(s.from.x - s.to.x) < 1e-6) continue;
      const at = (run) => (vertical ? run.from.x : run.from.y);
      const lo = (run) => Math.min(vertical ? run.from.y : run.from.x, vertical ? run.to.y : run.to.x);
      const hi = (run) => Math.max(vertical ? run.from.y : run.from.x, vertical ? run.to.y : run.to.x);
      if (Math.abs(at(r) - at(s)) < 1 && Math.min(hi(r), hi(s)) - Math.max(lo(r), lo(s)) > 1) return true;
    }
  }
  return false;
}

test("the table gives a pair the same sides whichever way it is asked", () => {
  for (const { buckets: [a, b], sides: [x, y] } of BFO_EDGE_RULES) {
    assert.deepEqual(sidesFor(a, b), { a: [x], b: [y] }, `${a} / ${b}`);
    assert.deepEqual(sidesFor(b, a), { a: [y], b: [x] }, `${b} / ${a}`);
  }
});

test("the pairs the table leaves free are free", () => {
  const free = [
    ["GDC", "GDC"], ["Quality", "Quality"], ["Material Entity", "Material Entity"], ["Realizable", "Realizable"], ["Process", "Process"],
    ["Material Entity", "Site"], ["GDC", "Quality"], ["Quality", "Realizable"],
    ["Temporal Region", "Site"], ["Temporal Region", "GDC"], ["Temporal Region", "Material Entity"], ["Temporal Region", "Quality"], ["Temporal Region", "Realizable"],
    ["Entity", "GDC"], ["Unknown", "Process"], ["Other", "Site"], ["Entity", "Unknown"],
  ];
  for (const [a, b] of free) {
    assert.equal(sidesFor(a, b), null, `${a} / ${b}`);
    assert.equal(sidesFor(b, a), null, `${b} / ${a}`);
  }
});

test("every rule is routed on its sides, in at most three bends, without sharing a track", () => {
  const { cards, edges, boxes } = arrange(() =>
    BFO_EDGE_RULES.map(({ buckets: [a, b], sides: [x, y] }) => ({ source: cardFor(a, x), target: cardFor(b, y) })),
  );
  const bucketOf = new Map(cards.map((card) => [card.id, card.bucket]));
  const reports = [];
  const routes = routeEdges(boxes, edges, { sidesFor: edgeSides((id) => bucketOf.get(id)), report: (r) => reports.push(r) });

  assert.equal(edges.length, BFO_EDGE_RULES.length);
  BFO_EDGE_RULES.forEach(({ buckets: [a, b], sides: [x, y] }, i) => {
    const points = routes.get(`e${i}`);
    const name = `${a} ${x} / ${b} ${y}`;
    assert.equal(borderOf(points[0], boxes.get(edges[i].source)), x, `${name}: start side`);
    assert.equal(borderOf(points[points.length - 1], boxes.get(edges[i].target)), y, `${name}: end side`);
    assert.ok(points.length - 2 <= 3, `${name}: ${points.length - 2} bends`);
  });
  assert.deepEqual(reports, [], "nothing was reported");

  const all = [...routes];
  for (let i = 0; i < all.length; i += 1) {
    for (let j = i + 1; j < all.length; j += 1) {
      assert.equal(shareATrack(all[i][1], all[j][1]), false, `${all[i][0]} and ${all[j][0]} share a track`);
    }
  }
});

test("a side the cards leave no way out of falls back to free choice, and says so", () => {
  // A (Material Entity) and B (GDC) are to leave and enter by their bottoms, but a
  // wall touches the bottom of A: nothing can leave that way.
  const boxes = new Map([
    ["A", { left: 0, right: 100, top: 0, bottom: 60 }],
    ["B", { left: 300, right: 400, top: 0, bottom: 60 }],
    ["wall", { left: -60, right: 160, top: 60, bottom: 120 }],
  ]);
  const bucketOf = new Map([["A", "Material Entity"], ["B", "GDC"], ["wall", "Other"]]);
  const reports = [];
  const routes = routeEdges(boxes, [{ id: "ab", source: "A", target: "B" }], {
    sidesFor: edgeSides((id) => bucketOf.get(id)),
    report: (r) => reports.push(r),
  });
  const points = routes.get("ab");
  assert.ok(points.length >= 2, "still routed");
  assert.notEqual(borderOf(points[0], boxes.get("A")), "S", "left A by a side that was free");
  assert.deepEqual(reports.map((r) => [r.type, r.edge.id]), [["fallback", "ab"]]);
});

test("a connector needing more than three bends is reported, not hidden", () => {
  // Process to Material Entity is west to west; the wall to the west of A forces a longer way round.
  const boxes = new Map([
    ["P1", { left: 400, right: 500, top: 0, bottom: 60 }],
    ["P2", { left: 200, right: 300, top: 0, bottom: 60 }], // stands west of P1: P1's west is walled in
    ["M", { left: 0, right: 100, top: 300, bottom: 360 }],
  ]);
  const bucketOf = new Map([["P1", "Process"], ["P2", "Process"], ["M", "Material Entity"]]);
  const reports = [];
  const routes = routeEdges(boxes, [{ id: "pm", source: "P1", target: "M" }], {
    sidesFor: edgeSides((id) => bucketOf.get(id)),
    report: (r) => reports.push(r),
  });
  // West out of P1 into the gap, down, west under P2, down, and east into M: four bends.
  assert.equal(borderOf(routes.get("pm")[0], boxes.get("P1")), "W", "still leaves by the required side");
  assert.equal(routes.get("pm").length - 2, 4);
  assert.deepEqual(reports.map((r) => [r.type, r.bends]), [["bends", 4]]);
});
