import { describe, expect, it } from 'vitest';

import {
  DEFAULT_BASEMAP_ID,
  MAPS_BASEMAPS,
  NATURAL_EARTH_BASEMAP_ID,
  basemapPreviewSrc,
  normalizeBasemapId,
} from './maps-basemaps';

describe('normalizeBasemapId', () => {
  it('accepts the Natural Earth countries basemap', () => {
    expect(normalizeBasemapId(NATURAL_EARTH_BASEMAP_ID)).toBe(NATURAL_EARTH_BASEMAP_ID);
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

describe('basemapPreviewSrc', () => {
  it('uses an SVG preview for Natural Earth', () => {
    expect(basemapPreviewSrc(NATURAL_EARTH_BASEMAP_ID)).toBe('/maps/basemaps/natural-earth.svg');
  });
});
