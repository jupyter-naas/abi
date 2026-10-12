import { describe, expect, it } from 'vitest';
import type { MapsPinMarker } from './leaflet-map';
import {
  clusterPinsByCountry,
  countryClusterLayers,
  COUNTRY_CLUSTER_EXPAND_ZOOM,
  groupAreaAt,
  resolveClusterMemberPins,
  shouldClusterPinsByCountry,
} from './maps-country-cluster';

function pin(partial: Partial<MapsPinMarker> & Pick<MapsPinMarker, 'id' | 'lat' | 'lng' | 'label'>): MapsPinMarker {
  return partial as MapsPinMarker;
}

describe('maps-country-cluster', () => {
  it('clusters multiple pins in the same country', () => {
    const pins = [
      pin({ id: 'a', lat: 48, lng: 2, label: 'Paris', country: 'France' }),
      pin({ id: 'b', lat: 43, lng: 1, label: 'Toulouse', country: 'France' }),
      pin({ id: 'c', lat: 51, lng: -0.1, label: 'London', country: 'United Kingdom' }),
    ];
    const out = clusterPinsByCountry(pins);
    expect(out).toHaveLength(2);
    const fr = out.find((p) => p.country === 'France');
    expect(fr?.clusterCount).toBe(2);
    expect(fr?.memberIds).toEqual(['a', 'b']);
    // Single-site countries get a numbered marker too.
    const uk = out.find((p) => p.country === 'United Kingdom');
    expect(uk?.clusterCount).toBe(1);
    expect(uk?.memberIds).toEqual(['c']);
  });

  it('leaves pins without country unclustered', () => {
    const pins = [pin({ id: 'x', lat: 0, lng: 0, label: 'Unknown' })];
    expect(clusterPinsByCountry(pins)).toEqual(pins);
  });

  it('respects zoom and view for shouldClusterPinsByCountry', () => {
    expect(shouldClusterPinsByCountry(true, COUNTRY_CLUSTER_EXPAND_ZOOM - 1, 'addresses')).toBe(true);
    expect(shouldClusterPinsByCountry(true, COUNTRY_CLUSTER_EXPAND_ZOOM, 'addresses')).toBe(false);
    expect(shouldClusterPinsByCountry(false, 2, 'addresses')).toBe(false);
    expect(shouldClusterPinsByCountry(true, 2, 'coverage')).toBe(false);
  });

  it('resolveClusterMemberPins expands member ids', () => {
    const all = [
      pin({ id: 'a', lat: 1, lng: 1, label: 'A', country: 'France' }),
      pin({ id: 'b', lat: 2, lng: 2, label: 'B', country: 'France' }),
    ];
    const cluster = clusterPinsByCountry(all)[0]!;
    expect(resolveClusterMemberPins(cluster, all)).toHaveLength(2);
  });

  it('numbers each layer separately in its default color', () => {
    const pins = [
      pin({ id: 'fm:1', lat: 48, lng: 2, label: 'Paris', country: 'France', layerId: 'fm', color: '#171c8f' }),
      pin({ id: 'fm:2', lat: 45, lng: 4, label: 'Lyon', country: 'France', layerId: 'fm', color: '#171c8f' }),
      pin({ id: 'va:1', lat: 49, lng: 2, label: 'Cergy', country: 'France', layerId: 'va', color: '#00a651' }),
    ];
    const titles: Record<string, string> = { fm: 'Forvis Mazars', va: 'Valeo' };
    const [fr] = clusterPinsByCountry(pins, (p) => titles[p.layerId ?? '']);
    expect(fr?.clusterCount).toBe(3);
    expect(fr?.clusterLayers).toEqual([
      { layerId: 'fm', title: 'Forvis Mazars', color: '#171c8f', count: 2 },
      { layerId: 'va', title: 'Valeo', color: '#00a651', count: 1 },
    ]);
    expect(fr?.detail).toBe('2 Forvis Mazars · 1 Valeo');
  });

  it('countryClusterLayers groups pins without a layer together', () => {
    const layers = countryClusterLayers([
      pin({ id: 'a', lat: 0, lng: 0, label: 'A', color: '#ff0000' }),
      pin({ id: 'b', lat: 0, lng: 0, label: 'B' }),
    ]);
    expect(layers).toEqual([{ layerId: '', title: undefined, color: '#ff0000', count: 2 }]);
  });

  it('places a country on its label point and merges spellings', () => {
    const centers = new Map([
      ['brazil', { name: 'Brazil', lat: -10, lng: -52 }],
      ['brasil', { name: 'Brazil', lat: -10, lng: -52 }],
    ]);
    const out = clusterPinsByCountry(
      [
        pin({ id: 'a', lat: -23, lng: -46, label: 'São Paulo', country: 'Brasil', layerId: 'edf-solar', color: '#fe5815' }),
        pin({ id: 'b', lat: -22, lng: -43, label: 'Rio', country: 'Brazil', layerId: 'valeo-power', color: '#00a651' }),
      ],
      { centers },
    );
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ label: 'Brazil', lat: -10, lng: -52, clusterCount: 2 });
  });

  it('groups by feed, counting a site in two layers once', () => {
    const site = { lat: 48, lng: 2, label: 'Cergy', country: 'France', feedId: 'valeo', feedColor: '#00a651', feedTitle: 'Valeo', featureId: 'cergy' };
    const out = clusterPinsByCountry(
      [
        pin({ ...site, id: 'valeo-power:cergy', layerId: 'valeo-power', color: '#00a651' }),
        pin({ ...site, id: 'valeo-light:cergy', layerId: 'valeo-light', color: '#00a651' }),
        pin({ id: 'edf-solar:x', lat: 45, lng: 4, label: 'Lyon', country: 'France', layerId: 'edf-solar', feedId: 'edf', feedColor: '#fe5815', feedTitle: 'EDF', color: '#fe5815' }),
      ],
      { groupBy: 'feed' },
    );
    expect(out[0]?.clusterLayers).toEqual([
      { layerId: 'valeo', title: 'Valeo', color: '#00a651', count: 1 },
      { layerId: 'edf', title: 'EDF', color: '#fe5815', count: 1 },
    ]);
    expect(out[0]?.clusterCount).toBe(2);
  });

  it('groups until zoom 5; continents first when asked', () => {
    expect(COUNTRY_CLUSTER_EXPAND_ZOOM).toBe(5);
    expect(groupAreaAt('feed', 'country', 4, 'addresses')).toBe('country');
    expect(groupAreaAt('feed', 'country', 5, 'addresses')).toBeNull();
    expect(groupAreaAt('off', 'country', 2, 'addresses')).toBeNull();
    expect(groupAreaAt('layer', 'continent', 2, 'addresses')).toBe('continent');
    expect(groupAreaAt('layer', 'continent', 3, 'addresses')).toBe('country');
    expect(groupAreaAt('feed', 'country', 2, 'coverage')).toBeNull();
  });

  it('groups countries into their continent', () => {
    const centers = new Map([
      ['france', { name: 'France', lat: 46.7, lng: 2.55, continent: 'Europe' }],
      ['germany', { name: 'Germany', lat: 51, lng: 10, continent: 'Europe' }],
    ]);
    const out = clusterPinsByCountry(
      [
        pin({ id: 'a', lat: 48, lng: 2, label: 'Paris', country: 'France', layerId: 'l' }),
        pin({ id: 'b', lat: 52, lng: 13, label: 'Berlin', country: 'Germany', layerId: 'l' }),
        pin({ id: 'c', lat: 1, lng: 103, label: 'Singapore', country: 'Singapore', layerId: 'l' }),
      ],
      { centers, area: 'continent' },
    );
    const europe = out.find((p) => p.label === 'Europe');
    expect(europe).toMatchObject({ clusterCount: 2, lat: 52, lng: 15, country: undefined });
    // No known continent: the country stays its own group.
    expect(out.find((p) => p.label === 'Singapore')?.clusterCount).toBe(1);
  });
});
