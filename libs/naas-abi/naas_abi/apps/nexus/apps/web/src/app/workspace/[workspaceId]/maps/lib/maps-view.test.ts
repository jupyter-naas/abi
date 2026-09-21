import { describe, expect, it } from 'vitest';
import {
  formatMapsFeedAge,
  isMapsViewportQuery,
  mapsNmBetween,
  mapsViewFromBounds,
  withMapsView,
} from './maps-view';

describe('mapsViewFromBounds', () => {
  it('caps radius at 250nm and requires zoom 4 for a viewport query', () => {
    const world = mapsViewFromBounds({
      west: -180,
      south: -85,
      east: 180,
      north: 85,
      lat: 20,
      lng: 0,
      zoom: 2,
    });
    expect(world.radiusNm).toBe(250);
    expect(isMapsViewportQuery(world)).toBe(false);

    const london = mapsViewFromBounds({
      west: -1,
      south: 51,
      east: 1,
      north: 52,
      lat: 51.5,
      lng: -0.1,
      zoom: 8,
    });
    expect(london.radiusNm).toBeGreaterThan(25);
    expect(london.radiusNm).toBeLessThan(250);
    expect(isMapsViewportQuery(london)).toBe(true);
  });

  it('appends viewport query params without dropping an existing query', () => {
    const view = mapsViewFromBounds({
      west: -1,
      south: 51,
      east: 1,
      north: 52,
      lat: 51.5,
      lng: -0.1,
      zoom: 8,
    });
    expect(withMapsView('/api/maps/flights', view)).toContain('lat=51.5000');
    expect(withMapsView('/api/maps/ais?x=1', view)).toContain('x=1');
    expect(withMapsView('/api/maps/ais?x=1', view)).toContain('radiusNm=');
  });
});

describe('mapsNmBetween / formatMapsFeedAge', () => {
  it('measures a short hop in nautical miles', () => {
    expect(mapsNmBetween(51.5, -0.1, 51.5, -0.1)).toBe(0);
    expect(mapsNmBetween(0, 0, 0, 1)).toBeGreaterThan(50);
    expect(mapsNmBetween(0, 0, 0, 1)).toBeLessThan(70);
  });

  it('formats observation age', () => {
    const now = Date.parse('2026-09-21T00:00:00Z');
    expect(formatMapsFeedAge('2026-09-21T00:00:00Z', now)).toBe('just now');
    expect(formatMapsFeedAge('2026-09-20T23:59:40Z', now)).toBe('20s ago');
    expect(formatMapsFeedAge('2026-09-20T23:50:00Z', now)).toBe('10m ago');
    expect(formatMapsFeedAge('not-a-date', now)).toBe('');
  });
});
