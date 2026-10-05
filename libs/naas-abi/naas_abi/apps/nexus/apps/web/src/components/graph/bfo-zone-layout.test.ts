import { describe, expect, it } from 'vitest';
import { bfoZoneLayout, zoneParents, type ZoneCard } from './bfo-zone-layout';

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
  it('puts a subclass right of its parent class in the zone', () => {
    const layout = bfoZoneLayout([
      card('act', 'Process'),
      card('region', 'Temporal Region'),
      { ...card('instant', 'Temporal Region'), parent: 'region' },
      { ...card('time-instant', 'Temporal Region'), parent: 'instant' },
      { ...card('date', 'Temporal Region'), parent: 'instant' },
      card('person', 'Material Entity'),
    ], []);
    const at = (id: string) => layout.positions.get(id)!;
    expect(at('instant').x).toBeGreaterThan(at('region').x);
    expect(at('instant').y).toBe(at('region').y);
    expect(at('date').x).toBeGreaterThan(at('instant').x);
    expect(at('time-instant').x).toBe(at('date').x);
    expect(at('date').y).toBe(at('instant').y);
    expect(at('time-instant').y).toBeGreaterThan(at('date').y);
    const temporal = layout.zones.find(zone => zone.key === 'Temporal Region')!;
    for (const id of ['region', 'instant', 'time-instant', 'date']) expect(inside(at(id), temporal)).toBe(true);
    const process = layout.zones.find(zone => zone.key === 'Process')!;
    expect(process.x + process.width).toBeLessThanOrEqual(temporal.x);
  });

  it('puts a continuant subclass below its parent class, siblings side by side', () => {
    const layout = bfoZoneLayout([
      card('act', 'Process'),
      card('material', 'Material Entity'),
      { ...card('person', 'Material Entity'), parent: 'material' },
      { ...card('org', 'Material Entity'), parent: 'material' },
      { ...card('employee', 'Material Entity'), parent: 'person' },
      card('loose', 'Material Entity'),
    ], []);
    const at = (id: string) => layout.positions.get(id)!;
    // Parents on top.
    expect(at('person').y).toBeGreaterThan(at('material').y);
    expect(at('employee').y).toBeGreaterThan(at('person').y);
    // Siblings on one row, by label; the first child under its parent.
    expect(at('org').y).toBe(at('person').y);
    expect(at('person').x).toBeGreaterThan(at('org').x);
    expect(at('org').x).toBe(at('material').x);
    expect(at('employee').x).toBe(at('person').x);
    // Cards outside the hierarchy come below it.
    expect(at('loose').y).toBeGreaterThan(at('employee').y);
    const zone = layout.zones.find(item => item.key === 'Material Entity')!;
    for (const id of ['material', 'person', 'org', 'employee', 'loose']) expect(inside(at(id), zone)).toBe(true);
  });

  it('finds the nearest superclass card in the same zone, through equivalents', () => {
    const BFO = 'http://purl.obolibrary.org/obo/';
    const parents = zoneParents([
      { id: 'region', bucket: 'Temporal Region', iri: 'abi:TemporalRegion', equivalents: [`${BFO}BFO_0000008`] },
      { id: 'instant', bucket: 'Temporal Region', iri: 'abi:TemporalInstant', equivalents: [`${BFO}BFO_0000203`], ancestors: ['abi:TemporalRegion', `${BFO}BFO_0000008`] },
      { id: 'time', bucket: 'Temporal Region', iri: 'time:Instant', ancestors: [`${BFO}BFO_0000203`, `${BFO}BFO_0000148`, `${BFO}BFO_0000008`] },
      { id: 'bfo-instant', bucket: 'Temporal Region', iri: `${BFO}BFO_0000203`, ancestors: ['abi:TemporalInstant', `${BFO}BFO_0000148`] },
      { id: 'act', bucket: 'Process', iri: 'abi:Act', ancestors: ['abi:TemporalRegion'] },
    ]);
    expect(parents.get('instant')).toBe('region');
    expect(parents.get('time')).toBe('instant');
    // Equivalent to abi:TemporalInstant: not its child.
    expect(parents.get('bfo-instant')).toBeUndefined();
    expect(parents.get('act')).toBeUndefined();
  });
});
