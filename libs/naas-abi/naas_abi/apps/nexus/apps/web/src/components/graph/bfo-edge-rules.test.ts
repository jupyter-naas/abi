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
