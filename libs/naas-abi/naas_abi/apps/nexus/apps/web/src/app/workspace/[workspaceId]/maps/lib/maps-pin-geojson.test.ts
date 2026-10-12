import { describe, expect, it } from 'vitest';

import { pinToFeature, pinsToFeatureCollection } from './maps-pin-geojson';
import type { MapsPinMarker } from './leaflet-map';

describe('maps-pin-geojson', () => {
  it('maps a pin to a GeoJSON Point feature', () => {
    const pin: MapsPinMarker = {
      id: 'eq-1',
      lat: 48.8,
      lng: 2.3,
      label: 'M4.2 · France',
      detail: 'USGS',
      classLabel: 'moderate',
    };
    const feature = pinToFeature(pin);
    expect(feature.geometry).toEqual({ type: 'Point', coordinates: [2.3, 48.8] });
    expect(feature.properties?.label).toBe('M4.2 · France');
    expect(feature.properties?.classLabel).toBe('moderate');
  });

  it('builds a FeatureCollection with nexus metadata', () => {
    const fc = pinsToFeatureCollection(
      [{ id: 'a', lat: 0, lng: 0, label: 'A' }],
      { layerId: 'earthquakes', layerTitle: 'Earthquakes', fetchedAt: '2026-01-01T00:00:00.000Z', featureCount: 0 },
    );
    expect(fc.type).toBe('FeatureCollection');
    expect(fc.features).toHaveLength(1);
    expect(fc.nexus?.layerId).toBe('earthquakes');
    expect(fc.nexus?.featureCount).toBe(1);
  });
});
