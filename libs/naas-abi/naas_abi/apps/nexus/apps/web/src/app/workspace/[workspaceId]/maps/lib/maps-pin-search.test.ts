import { describe, expect, it } from 'vitest';

import type { MapsPinMarker } from './leaflet-map';
import { searchMapPins } from './maps-pin-search';

const pin = (partial: Partial<MapsPinMarker> & Pick<MapsPinMarker, 'id' | 'lat' | 'lng' | 'label'>): MapsPinMarker =>
  partial as MapsPinMarker;

describe('searchMapPins', () => {
  const pins = [
    pin({ id: 'a', lat: 0, lng: 0, label: 'Tokyo HQ', country: 'Japan', detail: 'Office' }),
    pin({ id: 'b', lat: 1, lng: 1, label: 'Paris', country: 'France' }),
  ];

  it('returns empty for blank query', () => {
    expect(searchMapPins(pins, '   ')).toEqual([]);
  });

  it('matches label and country on enter-style query', () => {
    expect(searchMapPins(pins, 'tokyo').map((p) => p.id)).toEqual(['a']);
    expect(searchMapPins(pins, 'france').map((p) => p.id)).toEqual(['b']);
  });

  it('respects limit', () => {
    expect(searchMapPins(pins, 'a', 1)).toHaveLength(1);
  });
});
