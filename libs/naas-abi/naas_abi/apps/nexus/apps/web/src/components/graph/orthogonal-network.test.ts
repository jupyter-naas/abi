import test from 'node:test';
import assert from 'node:assert/strict';
import type { Network } from 'vis-network/standalone';
import { installOrthogonalEdges, type RoutedEdge } from './orthogonal-network';
import type { Point } from './orthogonal-route';

test('canvas routing keeps edge IDs, labels, arrows, selection and dragging; teardown restores the network', (t) => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'getComputedStyle');
  Object.defineProperty(globalThis, 'getComputedStyle', {configurable: true, value: () => ({getPropertyValue: () => '#ffffff'})});
  t.after(() => { if (descriptor) Object.defineProperty(globalThis, 'getComputedStyle', descriptor); else Reflect.deleteProperty(globalThis, 'getComputedStyle'); });
  let scale = 1;
  const positions: Record<string, Point> = { a: {x: 0, y: 0}, b: {x: 420, y: 200} };
  const listeners = new Map<string, (ctx: CanvasRenderingContext2D) => void>();
  const domListeners = new Map<string, unknown>();
  const canvas = { style: { cursor: '' } };
  let current: Point[] = [];
  const strokes: Point[][] = [], fills: Point[][] = [], texts: string[] = [], widths: number[] = [];
  const context = {
    save() {}, restore() {}, setLineDash() {}, beginPath() { current = []; }, closePath() {},
    moveTo(x: number, y: number) { current.push({x, y}); }, lineTo(x: number, y: number) { current.push({x, y}); },
    stroke() { strokes.push([...current]); }, fill() { fills.push([...current]); }, fillRect() {},
    fillText(text: string) { texts.push(text); }, measureText(text: string) { return {width: text.length * 6}; },
    set lineWidth(value: number) { widths.push(value); },
  } as unknown as CanvasRenderingContext2D;
  const net = {
    on(event: string, fn: (ctx: CanvasRenderingContext2D) => void) { listeners.set(event, fn); },
    off(event: string) { listeners.delete(event); },
    redraw() { listeners.get('beforeDrawing')?.(context); },
    getPositions() { return positions; }, getScale() { return scale; },
    getBoundingBox(id: string) { const p = positions[id]; return {left: p.x - 60, right: p.x + 60, top: p.y - 25, bottom: p.y + 25}; },
  };
  const container = {
    querySelector() { return canvas; },
    addEventListener(event: string, fn: unknown) { domListeners.set(event, fn); },
    removeEventListener(event: string) { domListeners.delete(event); },
  } as unknown as HTMLElement;
  const edges: RoutedEdge[] = [{id: 'restriction', source: 'a', target: 'b', style: {
    label: 'has participant (some)', width: 1, dashes: [5, 5], color: '#8899aa',
    arrows: {to: {enabled: true}}, font: {background: '#ffffff'},
  }}];
  const state = {edges, selected: [] as string[]};
  const renderer = installOrthogonalEdges(net as unknown as Network, container, () => state);
  assert.equal(strokes.length, 1); assert.equal(fills.length, 1); assert.equal(texts[0], edges[0].style.label);
  const route = strokes[0], a = route[0], b = route[1], middle = {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2};
  assert.equal(renderer.hitTest(middle), 'restriction');
  const tip = fills[0][0]; assert.deepEqual(tip, route[route.length - 1]);
  assert.equal(renderer.hitTest({x: -300, y: -300}), null);
  scale = 0.5;
  const near = a.y === b.y ? {...middle, y: middle.y + 10} : {...middle, x: middle.x + 10};
  assert.equal(renderer.hitTest(near), 'restriction', 'Hit tolerance stays six screen pixels at every zoom');
  state.selected = ['restriction']; net.redraw(); assert.ok(widths.at(-1)! > widths[0]);
  positions.b = {x: 700, y: 320}; net.redraw();
  assert.notDeepEqual(strokes.at(-1), route, 'Endpoint follows the dragged node');
  state.edges = []; net.redraw(); assert.equal(renderer.hitTest(middle), null);
  renderer.destroy();
  assert.equal(listeners.size, 0); assert.equal(domListeners.size, 0); assert.equal(canvas.style.cursor, '');
});
