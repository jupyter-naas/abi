import { describe, expect, it } from 'vitest';

import {
  getMapsDataset,
  getMapsDatasetsByCategory,
  isMapsDatasetId,
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
  'news',
  'ais',
  'iss',
] as const;

describe('MAPS_DATASETS taxonomy', () => {
  it('groups sources like Search: Public, Private, Custom', () => {
    expect(getMapsDatasetsByCategory('public').map((d) => d.id)).toEqual([
      ...PUBLIC_IDS,
    ]);
    expect(getMapsDatasetsByCategory('private').map((d) => d.id)).toEqual([
      'presence',
    ]);
    expect(getMapsDatasetsByCategory('custom').map((d) => d.id)).toEqual([
      'wog',
    ]);
  });

  it('marks WOG as Custom and Here as Private', () => {
    expect(getMapsDataset('wog')?.category).toBe('custom');
    expect(getMapsDataset('presence')?.category).toBe('private');
  });

  it('exposes Maps-owned public feed URLs and /api/maps proxies', () => {
    expect(MAPS_PUBLIC_FEEDS.earthquakes).toContain('earthquake.usgs.gov');
    expect(MAPS_PUBLIC_FEEDS.naturalEarth).toContain('natural-earth-vector');
    expect(MAPS_PUBLIC_FEEDS.wildfires).toContain('eonet.gsfc.nasa.gov');
    expect(MAPS_PUBLIC_FEEDS.eonetAll).toContain('eonet.gsfc.nasa.gov');
    expect(MAPS_PUBLIC_FEEDS.volcanoes).toContain('category=volcanoes');
    expect(MAPS_PUBLIC_FEEDS.firmsWms).toContain('firms.modaps.eosdis.nasa.gov');
    expect(MAPS_PUBLIC_FEEDS.temperature).toContain('open-meteo.com');
    expect(MAPS_PUBLIC_FEEDS.gdacs).toBe('/api/maps/gdacs');
    expect(MAPS_PUBLIC_FEEDS.openaq).toBe('/api/maps/openaq');
    expect(MAPS_PUBLIC_FEEDS.nwsAlerts).toBe('/api/maps/nws');
    expect(MAPS_PUBLIC_FEEDS.tropicalStorms).toBe('/api/maps/nhc');
    expect(MAPS_PUBLIC_FEEDS.flights).toBe('/api/maps/flights');
    expect(MAPS_PUBLIC_FEEDS.news).toBe('/api/maps/news');
    expect(MAPS_PUBLIC_FEEDS.ais).toBe('/api/maps/ais');
    expect(MAPS_PUBLIC_FEEDS.iss).toBe('/api/maps/iss');
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
