import { describe, expect, it } from 'vitest';
import { BFO_EDGE_RULES, edgeSides, sideLoads, sidesFor, type Side } from './bfo-edge-rules';
import { bfoZoneLayout } from './bfo-zone-layout';
import { routeEdges, type RouteFinding } from './orthogonal-grid-route';
import type { Box, Point } from './orthogonal-route';

const BUCKETS = ['Process', 'Temporal Region', 'Material Entity', 'Site', 'GDC', 'Quality', 'Realizable'];
const WIDTH = 140;
const HEIGHT = 64;

/** Two cards for each bucket, laid out in the BFO zones with the edge rules, as the network does. */
function arrange(edges: { source: string; target: string }[]) {
  const cards = BUCKETS.flatMap(bucket => [1, 2].map(n => ({ id: `${bucket} ${n}`, label: `${bucket} ${n}`, bucket, width: WIDTH, height: HEIGHT })));
  const bucketOf = new Map(cards.map(card => [card.id, card.bucket]));
  const links = edges.map((edge, i) => ({ id: `e${i}`, ...edge }));
  const rules = edgeSides(id => bucketOf.get(id));
  const layout = bfoZoneLayout(cards, links, { aspect: 1.8, sidesFor: rules });
  const boxes = new Map<string, Box>(cards.map(card => {
    const at = layout.positions.get(card.id)!;
    return [card.id, { left: at.x - WIDTH / 2, right: at.x + WIDTH / 2, top: at.y - HEIGHT / 2, bottom: at.y + HEIGHT / 2 }];
  }));
  const findings: RouteFinding[] = [];
  const routes = routeEdges(boxes, links, { sidesFor: rules, room: layout.room, report: finding => findings.push(finding) });
  return { links, boxes, routes, findings, layout };
}

/** Which border of ``box`` a point is on, away from its corners. */
function borderOf(point: Point, box: Box): Side {
  const near = (a: number, b: number) => Math.abs(a - b) < 1e-6;
  const within = (v: number, lo: number, hi: number) => v > lo + 1 && v < hi - 1;
  const sides: Side[] = [];
  if (near(point.y, box.top) && within(point.x, box.left, box.right)) sides.push('N');
  if (near(point.y, box.bottom) && within(point.x, box.left, box.right)) sides.push('S');
  if (near(point.x, box.left) && within(point.y, box.top, box.bottom)) sides.push('W');
  if (near(point.x, box.right) && within(point.y, box.top, box.bottom)) sides.push('E');
  expect(sides).toHaveLength(1);
  return sides[0];
}

describe('sidesFor', () => {
  it('gives the sides of each rule, whichever way the connector runs', () => {
    expect(sidesFor('Process', 'Temporal Region')).toEqual({ a: ['N'], b: ['N'] });
    expect(sidesFor('Quality', 'Process')).toEqual({ a: ['W'], b: ['E'] });
    expect(sidesFor('Process', 'GDC')).toEqual({ a: ['S'], b: ['W'] });
    expect(sidesFor('Site', 'Process')).toEqual({ a: ['N'], b: ['W'] });
    expect(sidesFor('Material Entity', 'Process')).toEqual({ a: ['W'], b: ['W'] });
    expect(sidesFor('Realizable', 'GDC')).toEqual({ a: ['S'], b: ['S'] });
  });

  it('leaves the pairs without a rule free', () => {
    expect(sidesFor('Process', 'Process')).toBeNull();
    expect(sidesFor('Material Entity', 'Site')).toBeNull();
    expect(sidesFor('GDC', 'Quality')).toBeNull();
    expect(sidesFor('Quality', 'Realizable')).toBeNull();
    expect(sidesFor('Temporal Region', 'Site')).toBeNull();
    expect(sidesFor('Process', 'Unknown')).toBeNull();
  });

  it('counts the connectors on each side of each card', () => {
    const rules = edgeSides(id => id.split(':')[0]);
    const loads = sideLoads([{ source: 'Process:a', target: 'Temporal Region:b' }, { source: 'Process:a', target: 'Site:c' }, { source: 'Site:c', target: 'Site:d' }], rules);
    expect(loads.get('Process:a')).toEqual({ N: 1, S: 0, E: 0, W: 1, free: 0 });
    expect(loads.get('Site:c')).toEqual({ N: 1, S: 0, E: 0, W: 0, free: 1 });
  });
});

describe('the BFO zone network', () => {
  it.each(BFO_EDGE_RULES.map(rule => [rule.buckets.join(' / '), rule] as const))('routes %s on the sides of its rule', (_name, rule) => {
    const [first, second] = rule.buckets;
    const { links, boxes, routes, findings } = arrange([{ source: `${first} 1`, target: `${second} 1` }]);
    const points = routes.get(links[0].id)!;
    expect(findings).toEqual([]);
    expect(borderOf(points[0], boxes.get(`${first} 1`)!)).toBe(rule.sides[0]);
    expect(borderOf(points[points.length - 1], boxes.get(`${second} 1`)!)).toBe(rule.sides[1]);
  });

  it('keeps every rule when all of them are drawn at once', () => {
    const { links, boxes, routes } = arrange(BFO_EDGE_RULES.map(rule => ({ source: `${rule.buckets[0]} 1`, target: `${rule.buckets[1]} 2` })));
    links.forEach((link, i) => {
      const points = routes.get(link.id)!;
      expect(borderOf(points[0], boxes.get(link.source)!)).toBe(BFO_EDGE_RULES[i].sides[0]);
      expect(borderOf(points[points.length - 1], boxes.get(link.target)!)).toBe(BFO_EDGE_RULES[i].sides[1]);
    });
  });

  it('widens the margins for the connectors the rules send round the outside', () => {
    const bare = arrange([]).layout.room!;
    const routed = arrange([
      { source: 'Process 1', target: 'Temporal Region 1' },
      { source: 'Process 1', target: 'Material Entity 1' },
      { source: 'Site 1', target: 'Quality 1' },
    ]).layout.room!;
    expect(routed.top).toBeGreaterThan(bare.top!);
    expect(routed.left).toBeGreaterThan(bare.left!);
    expect(routed.bottom).toBeGreaterThan(bare.bottom!);
  });
});

describe('facing cards', () => {
  const box = (x: number, y: number): Box => ({ left: x - WIDTH / 2, right: x + WIDTH / 2, top: y - HEIGHT / 2, bottom: y + HEIGHT / 2 });
  const rules = edgeSides(id => id.split(' ')[0] === 'P' ? 'Process' : id.split(' ')[0] === 'Q' ? 'Quality' : 'Temporal Region');

  it('joins a class and its subclass beside it with a straight connector', () => {
    // Temporal Region, then Temporal Instant to its right, in the occurrents.
    const boxes = new Map([['T region', box(0, 0)], ['T instant', box(260, 0)]]);
    const routes = routeEdges(boxes, [{ id: 'sub', source: 'T instant', target: 'T region' }], { sidesFor: rules });
    expect(routes.get('sub')).toEqual([{ x: 190, y: 0 }, { x: 70, y: 0 }]);
  });

  it('joins a class and its subclass below it with a straight connector', () => {
    const boxes = new Map([['T a', box(0, 0)], ['T b', box(0, 200)]]);
    const routes = routeEdges(boxes, [{ id: 'sub', source: 'T b', target: 'T a' }], { sidesFor: rules });
    expect(routes.get('sub')).toEqual([{ x: 0, y: 168 }, { x: 0, y: 32 }]);
  });

  it('bends round a card that stands between them', () => {
    const boxes = new Map([['T a', box(0, 0)], ['T b', box(260, 0)], ['T c', box(520, 0)]]);
    const routes = routeEdges(boxes, [{ id: 'skip', source: 'T a', target: 'T c' }], { sidesFor: rules });
    expect(routes.get('skip')!.length).toBeGreaterThan(2);
  });

  it('keeps a rule that sends the connector out by another side', () => {
    // Process / Temporal Region is a U over the top (N / N), even side by side.
    const boxes = new Map([['P a', box(0, 0)], ['T b', box(260, 0)]]);
    const points = routeEdges(boxes, [{ id: 'u', source: 'P a', target: 'T b' }], { sidesFor: rules }).get('u')!;
    expect(points[0].y).toBe(-32);
    expect(points[points.length - 1].y).toBe(-32);
  });

  it('gives the other connectors on that side their own ports', () => {
    // Process: its subclass to the right, and a Quality it reaches by its east side.
    const boxes = new Map([['P a', box(0, 0)], ['P b', box(260, 0)], ['Q c', box(260, 300)]]);
    const routes = routeEdges(boxes, [{ id: 'sub', source: 'P b', target: 'P a' }, { id: 'rule', source: 'P a', target: 'Q c' }], { sidesFor: rules });
    const straight = routes.get('sub')!;
    expect(straight).toHaveLength(2);
    const out = routes.get('rule')![0];
    expect(out.x).toBe(70);
    expect(Math.abs(out.y - straight[0].y)).toBeGreaterThanOrEqual(6);
  });
});

describe('a large drawing', () => {
  it('keeps the rules when it is routed coarse first, then fine', () => {
    // Twelve cards a bucket: enough for the two-level routing.
    const cards = BUCKETS.flatMap(bucket => Array.from({ length: 12 }, (_, n) => ({ id: `${bucket} ${n + 1}`, label: `${bucket} ${n + 1}`, bucket, width: WIDTH, height: HEIGHT })));
    const bucketOf = new Map(cards.map(card => [card.id, card.bucket]));
    const links = BFO_EDGE_RULES.map((rule, i) => ({ id: `e${i}`, source: `${rule.buckets[0]} 1`, target: `${rule.buckets[1]} 2` }));
    const rules = edgeSides(id => bucketOf.get(id));
    const layout = bfoZoneLayout(cards, links, { aspect: 1.8, sidesFor: rules });
    const boxes = new Map<string, Box>(cards.map(card => {
      const at = layout.positions.get(card.id)!;
      return [card.id, { left: at.x - WIDTH / 2, right: at.x + WIDTH / 2, top: at.y - HEIGHT / 2, bottom: at.y + HEIGHT / 2 }];
    }));
    const findings: RouteFinding[] = [];
    const routes = routeEdges(boxes, links, { sidesFor: rules, room: layout.room, report: finding => findings.push(finding) });
    expect(findings.filter(finding => finding.type === 'fallback')).toEqual([]);
    links.forEach((link, i) => {
      const points = routes.get(link.id)!;
      expect(borderOf(points[0], boxes.get(link.source)!)).toBe(BFO_EDGE_RULES[i].sides[0]);
      expect(borderOf(points[points.length - 1], boxes.get(link.target)!)).toBe(BFO_EDGE_RULES[i].sides[1]);
    });
  });
});

describe('straightening', () => {
  it('leaves no route with two bends where one will do', () => {
    // Two free cards diagonal to each other with nothing between: an L, not a Z.
    const box = (x: number, y: number): Box => ({ left: x - WIDTH / 2, right: x + WIDTH / 2, top: y - HEIGHT / 2, bottom: y + HEIGHT / 2 });
    const boxes = new Map([['T a', box(0, 0)], ['T b', box(400, 300)]]);
    const points = routeEdges(boxes, [{ id: 'l', source: 'T a', target: 'T b' }], { sidesFor: edgeSides(() => 'Temporal Region') }).get('l')!;
    expect(points).toHaveLength(3);
  });
});
