import test from 'node:test';
import assert from 'node:assert/strict';
import { crossesBox, orthogonalRoute, parallelLanes, routeDistance, routeLabel, type Box, type Point } from './orthogonal-route';
const box = (x: number, y: number): Box => ({ left: x - 60, right: x + 60, top: y - 25, bottom: y + 25 });
const onBoundary = (p: Point, b: Box) => ((p.x === b.left || p.x === b.right) && p.y >= b.top && p.y <= b.bottom) || ((p.y === b.top || p.y === b.bottom) && p.x >= b.left && p.x <= b.right);
function check(route: Point[], a: Box, b: Box) {
  assert.ok(route.length >= 2);
  assert.ok(onBoundary(route[0], a)); assert.ok(onBoundary(route[route.length - 1], b));
  for (let i = 1; i < route.length; i++) {
    assert.ok(Number.isFinite(route[i].x + route[i].y));
    assert.notDeepEqual(route[i], route[i - 1]);
    assert.ok(route[i].x === route[i - 1].x || route[i].y === route[i - 1].y, 'Every segment must be horizontal or vertical');
  }
}
test('all quadrants, aligned nodes, and close boxes connect at square boundaries', () => {
  for (const x of [-500, -150, 0, 80, 150, 500]) for (const y of [-350, -80, 0, 80, 350]) {
    const a = box(0, 0), b = box(x, y);
    for (const direction of [undefined, 'LR', 'TD'] as const) {
      const route = orthogonalRoute(a, b, {direction}); check(route, a, b);
      if (Math.abs(x) >= 150 || Math.abs(y) >= 80) for (let i = 1; i < route.length; i++) {
        assert.equal(crossesBox(route[i - 1], route[i], a), false, 'Do not reenter the source box');
        assert.equal(crossesBox(route[i - 1], route[i], b), false, 'Do not enter the target before the arrow');
      }
    }
  }
});
test('routes around an intervening node instead of crossing its label', () => {
  const a = box(0, 0), b = box(500, 0), obstacle = box(240, 0);
  const route = orthogonalRoute(a, b, {obstacles: [obstacle]}); check(route, a, b);
  for (let i = 1; i < route.length; i++) assert.equal(crossesBox(route[i - 1], route[i], obstacle), false);
});
test('parallel and reverse relationships get separate stable lanes', () => {
  const edges = [{id: 'one', source: 'a', target: 'b'}, {id: 'two', source: 'a', target: 'b'}, {id: 'reverse', source: 'b', target: 'a'}];
  const lanes = parallelLanes(edges);
  assert.deepEqual(parallelLanes([...edges].reverse()), lanes);
  const routes = edges.map(e => orthogonalRoute(box(e.source === 'a' ? 0 : 500, 0), box(e.target === 'a' ? 0 : 500, 0), lanes.get(e.id)));
  assert.equal(new Set(routes.map(route => JSON.stringify([...route].sort((a, b) => a.x - b.x)))).size, 3);
});
test('self relationships remain visible with distinct square loops', () => {
  const a = box(0, 0);
  const routes = [-1, 0, 1].map(lane => orthogonalRoute(a, a, {loop: true, lane, laneCount: 3}));
  for (const route of routes) { check(route, a, a); assert.ok(route.length >= 5); }
  assert.equal(new Set(routes.map(route => JSON.stringify(route))).size, 3);
});
test('hit testing follows the elbow, not the obsolete diagonal', () => {
  const route = [{x: 0, y: 0}, {x: 160, y: 0}, {x: 160, y: 200}, {x: 320, y: 200}];
  assert.equal(routeDistance({x: 160, y: 65}, route), 0);
  assert.equal(routeDistance({x: 80, y: 50}, route), 50);
  assert.deepEqual(routeLabel(route), {x: 160, y: 100, horizontal: false});
});

test('floating-point radial positions retain exact horizontal and vertical segments', () => {
  const a = box(0, 0), b = box(1.5065737213851678e-14, -182.2534522012996);
  check(orthogonalRoute(a, b), a, b);
});
