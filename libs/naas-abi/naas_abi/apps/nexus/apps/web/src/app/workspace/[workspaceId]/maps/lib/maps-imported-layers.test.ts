import { describe, expect, it } from 'vitest';

import {
  normalizeImportedGeoJson,
  parseGeoJsonLayerInput,
  slugifyLayerSlug,
} from './maps-imported-layers';

describe('maps-imported-layers', () => {
  it('slugifies titles into valid layer slugs', () => {
    expect(slugifyLayerSlug('My Sites')).toBe('my-sites');
    expect(slugifyLayerSlug('!!!')).toBe('layer');
  });

  it('parses FeatureCollection and legacy pins', () => {
    const fc = parseGeoJsonLayerInput(JSON.stringify({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          id: 'a',
          geometry: { type: 'Point', coordinates: [1, 2] },
          properties: { label: 'A' },
        },
      ],
    }));
    expect(fc.ok && fc.featureCount).toBe(1);

    const pins = normalizeImportedGeoJson({
      pins: [{ id: 'b', lat: 3, lng: 4, label: 'B' }],
    });
    expect(pins.ok && pins.featureCount).toBe(1);
  });

  it('rejects non-point collections', () => {
    const result = normalizeImportedGeoJson({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
          properties: {},
        },
      ],
    });
    expect(result.ok).toBe(false);
  });
});
