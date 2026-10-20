import test from 'node:test';
import assert from 'node:assert/strict';
import { compactNetworkPositions, type LayoutBox } from './compact-network-layout';
const boxes: LayoutBox[] = Array.from({length: 25}, (_, i) => ({id: String(i), label: 'Term ' + i, width: 128, height: i % 4 === 0 ? 86 : 64, primary: i === 0}));
const links = boxes.slice(1).map(box => ({source: '0', target: box.id}));
function extent(positions: ReturnType<typeof compactNetworkPositions>, boxes: LayoutBox[]) {
  return { width: Math.max(...boxes.map(box => positions.get(box.id)!.x + box.width / 2)) - Math.min(...boxes.map(box => positions.get(box.id)!.x - box.width / 2)),
    height: Math.max(...boxes.map(box => positions.get(box.id)!.y + box.height / 2)) - Math.min(...boxes.map(box => positions.get(box.id)!.y - box.height / 2)) };
}
test('25 terms fit at readable scale with room between their actual card boundaries', () => {
  const positions = compactNetworkPositions(boxes, links);
  const bounds = extent(positions, boxes);
  assert.ok(bounds.width * 1.1 <= 1000); assert.ok(bounds.height * 1.1 <= 700);
  for (const a of boxes) for (const b of boxes) if (a.id !== b.id) {
    const p = positions.get(a.id)!, q = positions.get(b.id)!;
    assert.ok(Math.abs(p.x - q.x) >= (a.width + b.width) / 2 + 40 || Math.abs(p.y - q.y) >= (a.height + b.height) / 2 + 40);
  }
  assert.deepEqual(positions.get('0'), {x: 0, y: 0});
});
test('spacing changes separation without removing terms, links, or their direction', () => {
  const original = structuredClone({boxes, links});
  const compact = extent(compactNetworkPositions(boxes, links, 40), boxes);
  const spacious = extent(compactNetworkPositions(boxes, links, 140), boxes);
  assert.ok(spacious.width > compact.width); assert.ok(spacious.height > compact.height);
  assert.deepEqual({boxes, links}, original);
});
test('order is deterministic, and loops, cycles, dangling links and disconnected nodes are safe', () => {
  const edges = [...links, {source: '2', target: '0'}, {source: '0', target: '0'}, {source: 'missing', target: '3'}];
  const first = compactNetworkPositions(boxes, edges);
  assert.deepEqual(compactNetworkPositions([...boxes].reverse(), [...edges].reverse()), first);
  assert.equal(compactNetworkPositions(boxes, []).size, boxes.length);
  assert.equal(compactNetworkPositions([], []).size, 0);
  assert.deepEqual(compactNetworkPositions([boxes[0]], []).get('0'), {x: 0, y: 0});
});
test('wide and tall cards determine cell size and retain connector clearance', () => {
  const large = boxes.map((box, i) => ({...box, width: i === 3 ? 220 : 128, height: i === 5 ? 132 : 64}));
  const positions = compactNetworkPositions(large, links, 0);
  for (const a of large) for (const b of large) if (a.id !== b.id) {
    const p = positions.get(a.id)!, q = positions.get(b.id)!;
    assert.ok(Math.abs(p.x - q.x) >= (a.width + b.width) / 2 + 36 || Math.abs(p.y - q.y) >= (a.height + b.height) / 2 + 36);
  }
});
