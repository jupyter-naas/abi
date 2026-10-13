import { describe, expect, it } from 'vitest';

import { DEFAULT_BASEMAP_ID, MAPS_BASEMAPS, normalizeBasemapId } from './maps-basemaps';

describe('normalizeBasemapId', () => {
  it('falls back to the default for unknown ids', () => {
    expect(normalizeBasemapId('natural-earth')).toBe(DEFAULT_BASEMAP_ID);
  });

  it('falls back to the default for other unknown ids', () => {
    expect(normalizeBasemapId('not-a-basemap')).toBe(DEFAULT_BASEMAP_ID);
    expect(normalizeBasemapId('cartodb-voyager')).toBe(DEFAULT_BASEMAP_ID);
  });

  it('keeps known basemap ids', () => {
    for (const def of MAPS_BASEMAPS) {
      expect(normalizeBasemapId(def.id)).toBe(def.id);
    }
  });
});
