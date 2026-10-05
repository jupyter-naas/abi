import { describe, expect, it } from 'vitest';
import { bfoZoneLayout, type ZoneCard } from './bfo-zone-layout';

const card = (id: string, bucket: string): ZoneCard => ({ id, bucket, label: id, width: 100, height: 60 });
const inside = (point: { x: number; y: number }, box: { x: number; y: number; width: number; height: number }) =>
  point.x > box.x && point.x < box.x + box.width && point.y > box.y && point.y < box.y + box.height;

describe('bfoZoneLayout', () => {
  it('puts occurrents in a band above continuants', () => {
    const layout = bfoZoneLayout(
      [card('act', 'Process'), card('when', 'Temporal Region'), card('person', 'Material Entity'), card('role', 'Realizable')],
      [{ source: 'act', target: 'person' }],
    );
    expect(layout.bands.map(band => band.label)).toEqual(['OCCURRENTS', 'CONTINUANTS']);
    const [occurrents, continuants] = layout.bands;
    expect(occurrents.y + occurrents.height).toBe(continuants.y);
    expect(inside(layout.positions.get('act')!, occurrents)).toBe(true);
    expect(inside(layout.positions.get('when')!, occurrents)).toBe(true);
    expect(inside(layout.positions.get('person')!, continuants)).toBe(true);
    expect(inside(layout.positions.get('role')!, continuants)).toBe(true);
  });

  it('gives each bucket its own zone, in the 7 buckets order', () => {
    const layout = bfoZoneLayout(
      [card('r', 'Realizable'), card('s', 'Site'), card('m', 'Material Entity'), card('p', 'Process'), card('t', 'Temporal Region')],
      [],
    );
    expect(layout.zones.map(zone => zone.key)).toEqual(['Process', 'Temporal Region', 'Material Entity', 'Site', 'Realizable']);
    for (const zone of layout.zones) {
      const members = ['r', 's', 'm', 'p', 't'].filter(id => inside(layout.positions.get(id)!, zone));
      expect(members).toHaveLength(1);
    }
    const [process, temporal] = layout.zones;
    expect(process.x).toBeLessThan(temporal.x);
    expect(process.width).toBeGreaterThan(temporal.width);
  });

  it('collects unresolved buckets in an Other zone with the continuants', () => {
    const layout = bfoZoneLayout([card('a', 'Unknown'), card('b', 'Entity')], []);
    expect(layout.zones.map(zone => zone.key)).toEqual(['Other']);
    expect(layout.bands.map(band => band.label)).toEqual(['CONTINUANTS']);
  });

  it('keeps cards from overlapping inside a crowded zone', () => {
    const cards = Array.from({ length: 12 }, (_, i) => card(`m${i}`, 'Material Entity'));
    const layout = bfoZoneLayout(cards, []);
    const points = cards.map(item => layout.positions.get(item.id)!);
    for (let i = 0; i < points.length; i++) {
      for (let j = i + 1; j < points.length; j++) {
        const apart = Math.abs(points[i].x - points[j].x) >= 100 || Math.abs(points[i].y - points[j].y) >= 60;
        expect(apart).toBe(true);
      }
    }
  });

  it('is empty without cards', () => {
    expect(bfoZoneLayout([], [])).toEqual({ positions: new Map(), zones: [], bands: [] });
  });
});
