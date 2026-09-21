import test from 'node:test';
import assert from 'node:assert/strict';
import { fitReadableViewport, spacingViewport } from './network-viewport';

test('changing spacing preserves text scale and the inspected area while expanding visible gaps', () => {
  const before = { left: { x: -400, y: 100 }, right: { x: 400, y: 100 } };
  const after = Object.entries(before).map(([id, point]) => ({ id, x: point.x * 1.7, y: point.y * 1.7 }));
  const viewport = { scale: 1.2, position: { x: 410, y: 105 } };
  const expanded = spacingViewport(viewport, before, after);
  assert.equal(expanded.scale, viewport.scale);
  assert.equal((after[1].x - expanded.position.x) * expanded.scale, (before.right.x - viewport.position.x) * viewport.scale);
  assert.equal((after[1].x - after[0].x) * expanded.scale, 800 * 1.7 * viewport.scale);
  const restored = spacingViewport(expanded, Object.fromEntries(after.map(node => [node.id, node])), Object.entries(before).map(([id, point]) => ({ id, ...point })));
  assert.deepEqual(restored, viewport);
  assert.deepEqual(spacingViewport(viewport, {}, [{ id: 'new' }]), viewport);
});

test('automatic framing retains readable text; manual Fit and non-ontology graphs can fit the whole graph', () => {
  let scale = .8;
  let position = { x: 10, y: 20 };
  const network = {
    getScale: () => scale,
    getViewPosition: () => position,
    fit: () => { scale = .3; position = { x: 0, y: 0 }; },
    moveTo: (target: { scale?: number; position?: { x: number; y: number } }) => {
      scale = target.scale ?? scale; position = target.position ?? position;
    },
  };
  fitReadableViewport(network, 1, 300);
  assert.equal(scale, 1);
  assert.deepEqual(position, { x: 0, y: 0 });
  network.fit(); assert.equal(scale, .3);
  fitReadableViewport(network, 0, 300); assert.equal(scale, .3);
  network.fit = () => { scale = 1.4; position = { x: 0, y: 0 }; };
  fitReadableViewport(network, 1, 300); assert.equal(scale, 1.4);
});
