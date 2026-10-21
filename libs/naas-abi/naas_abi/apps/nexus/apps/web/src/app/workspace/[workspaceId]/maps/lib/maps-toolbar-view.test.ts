import { describe, expect, it } from 'vitest';

import {
  formatMapsToolbarCenter,
  formatMapsToolbarViewLine,
  formatMapsToolbarZoom,
} from './maps-toolbar-view';

describe('maps-toolbar-view', () => {
  it('formats zoom and center for the toolbar', () => {
    expect(formatMapsToolbarZoom(5.4)).toBe('Zoom 5');
    expect(formatMapsToolbarCenter(48.8566, 2.3522)).toBe('48.86°N, 2.35°E');
  });

  it('joins view segments with basemap and optional radius', () => {
    expect(
      formatMapsToolbarViewLine({
        zoom: 8,
        lat: -33.87,
        lng: 151.21,
        basemapLabel: 'Street',
        radiusNm: 42.7,
      }),
    ).toBe('Zoom 8 · 33.87°S, 151.21°E · Street · ~43 nm view');
  });
});
