import { describe, expect, it } from 'vitest';
import { boxesOverlap, placeLabels } from './edge-labels';
import type { Box } from './orthogonal-route';

const card = (x: number, y: number): Box => ({ left: x - 60, right: x + 60, top: y - 30, bottom: y + 30 });

describe('placeLabels', () => {
  it('puts every label on its own route, clear of the others and of the cards', () => {
    // Three parallel connectors a track apart: their labels cannot all sit in the middle.
    const cards = [card(0, 0), card(400, 0), card(0, 100), card(400, 100), card(0, 200), card(400, 200)];
    const requests = [0, 6, 12].map((dy, k) => ({ id: `e${k}`, width: 70, height: 12, points: [{ x: 60, y: 100 + dy }, { x: 340, y: 100 + dy }] }));
    const placed = placeLabels(requests, cards);
    const boxes = [...placed.values()].map(label => label.box);
    expect(boxes).toHaveLength(3);
    for (let i = 0; i < boxes.length; i += 1) for (let j = i + 1; j < boxes.length; j += 1) expect(boxesOverlap(boxes[i], boxes[j])).toBe(false);
    for (const box of boxes) for (const c of cards) expect(boxesOverlap(box, c)).toBe(false);
    // Each on its own line.
    requests.forEach((request, k) => expect(placed.get(`e${k}`)!.y).toBe(request.points[0].y));
  });

  it('puts a label beside a vertical run, and keeps it in the frame', () => {
    const route = [{ x: 0, y: 30 }, { x: 0, y: 230 }];
    const frame = { left: -10, top: -40, right: 200, bottom: 300 };
    const label = placeLabels([{ id: 'v', width: 80, height: 12, points: route }], [card(0, 0), card(0, 260)], frame).get('v')!;
    // Not over the line: beside it, to the right since the left is outside the frame.
    expect(label.box.left).toBeGreaterThan(0);
    expect(label.box.top).toBeGreaterThan(30);
    expect(label.box.bottom).toBeLessThan(230);
  });

  it('prefers the middle of the run', () => {
    const label = placeLabels([{ id: 'h', width: 40, height: 12, points: [{ x: 0, y: 0 }, { x: 300, y: 0 }] }], []).get('h')!;
    expect(label.x).toBe(150);
  });
});
