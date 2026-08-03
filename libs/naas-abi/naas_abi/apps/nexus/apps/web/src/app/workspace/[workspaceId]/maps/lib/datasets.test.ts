import { describe, expect, it } from 'vitest';

import {
  getMapsDataset,
  getMapsDatasetsByCategory,
  isMapsDatasetId,
  mapsCustomFeedUrl,
  MAPS_DATASETS,
  MAPS_PUBLIC_FEEDS,
} from './datasets';
import { CONFLICT_SITES } from './conflict-sites';

const PUBLIC_IDS = [
  'openstreetmap',
  'earthquakes',
  'wildfires',
  'temperature',
  'natural-earth',
  'gdacs',
  'eonet-all',
  'openaq',
  'nws-alerts',
  'tropical-storms',
  'volcanoes',
  'flights',
  'conflict',
  'gulf-strikes',
  'news',
  'ais',
  'iss',
] as const;

describe('MAPS_DATASETS taxonomy', () => {
  it('groups sources like Search: Public, Private (Here), Custom (empty upstream)', () => {
    expect(getMapsDatasetsByCategory('public').map((d) => d.id)).toEqual([
      ...PUBLIC_IDS,
    ]);
    expect(getMapsDatasetsByCategory('private').map((d) => d.id)).toEqual([
      'presence',
    ]);
    // Custom is the extension point: product-specific layers are registered by a
    // deployment through NEXT_PUBLIC_MAPS_CUSTOM_DATASETS, never shipped here.
    expect(getMapsDatasetsByCategory('custom')).toEqual([]);
  });

  it('marks Here as Private and ships no product-specific datasets', () => {
    expect(getMapsDataset('presence')?.category).toBe('private');
    expect(getMapsDataset('ontologist-north-america')).toBeNull();
    expect(isMapsDatasetId('ontologist-north-america')).toBe(false);
    expect(getMapsDataset('wog')).toBeNull();
    expect(isMapsDatasetId('wog')).toBe(false);
  });

  it('exposes Maps-owned public feed URLs and /api/maps proxies', () => {
    expect(MAPS_PUBLIC_FEEDS.earthquakes).toContain('earthquake.usgs.gov');
    expect(MAPS_PUBLIC_FEEDS.naturalEarth).toContain('natural-earth-vector');
    expect(MAPS_PUBLIC_FEEDS.wildfires).toContain('eonet.gsfc.nasa.gov');
    expect(MAPS_PUBLIC_FEEDS.eonetAll).toContain('eonet.gsfc.nasa.gov');
    expect(MAPS_PUBLIC_FEEDS.volcanoes).toContain('category=volcanoes');
    expect(MAPS_PUBLIC_FEEDS.firms).toBe('/api/maps/firms');
    expect(MAPS_PUBLIC_FEEDS.temperature).toContain('open-meteo.com');
    expect(MAPS_PUBLIC_FEEDS.gdacs).toBe('/api/maps/gdacs');
    expect(MAPS_PUBLIC_FEEDS.openaq).toBe('/api/maps/openaq');
    expect(MAPS_PUBLIC_FEEDS.nwsAlerts).toBe('/api/maps/nws');
    expect(MAPS_PUBLIC_FEEDS.tropicalStorms).toBe('/api/maps/nhc');
    expect(MAPS_PUBLIC_FEEDS.flights).toBe('/api/maps/flights');
    expect(MAPS_PUBLIC_FEEDS.gulfStrikes).toBe('/api/maps/gulf-strikes');
    expect(MAPS_PUBLIC_FEEDS.news).toBe('/api/maps/news');
    expect(MAPS_PUBLIC_FEEDS.ais).toBe('/api/maps/ais');
    expect(MAPS_PUBLIC_FEEDS.iss).toBe('/api/maps/iss');
  });

  it('routes Custom datasets through the authed /api/maps/custom proxy', () => {
    expect(mapsCustomFeedUrl('acme-sites', 'ws-1')).toBe(
      '/api/maps/custom/acme-sites?workspace_id=ws-1',
    );
    expect(mapsCustomFeedUrl('acme sites/../x', 'ws 1')).toBe(
      '/api/maps/custom/acme%20sites%2F..%2Fx?workspace_id=ws+1',
    );
  });

  it('keeps a curated Maps-owned conflict pin list (no WSR import)', () => {
    expect(CONFLICT_SITES.length).toBeGreaterThanOrEqual(10);
    for (const site of CONFLICT_SITES) {
      expect(Number.isFinite(site.lat)).toBe(true);
      expect(Number.isFinite(site.lng)).toBe(true);
      expect(site.name.length).toBeGreaterThan(0);
    }
  });

  it('registers every dataset id', () => {
    for (const dataset of MAPS_DATASETS) {
      expect(isMapsDatasetId(dataset.id)).toBe(true);
    }
    expect(isMapsDatasetId('not-a-dataset')).toBe(false);
    expect(MAPS_DATASETS.filter((d) => d.category === 'public')).toHaveLength(
      PUBLIC_IDS.length,
    );
  });
});
