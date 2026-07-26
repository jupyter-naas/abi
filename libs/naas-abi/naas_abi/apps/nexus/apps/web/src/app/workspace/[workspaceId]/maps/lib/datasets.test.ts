import { describe, expect, it } from 'vitest';

import {
  getMapsDataset,
  getMapsDatasetsByCategory,
  isMapsDatasetId,
  MAPS_DATASETS,
  MAPS_PROXY_ROUTES,
  MAPS_PUBLIC_FEEDS,
} from './datasets';
import { CONFLICT_SITES } from './conflict-sites';

describe('MAPS_DATASETS taxonomy', () => {
  it('groups sources like Search: Public, Private, Custom', () => {
    expect(getMapsDatasetsByCategory('public').map((d) => d.id)).toEqual([
      'openstreetmap',
      'earthquakes',
      'wildfires',
      'temperature',
      'natural-earth',
      'gdacs',
      'eonet',
      'openaq',
      'nws',
      'nhc',
      'volcanoes',
      'flights',
      'conflict',
      'news',
      'ais',
      'iss',
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

  it('exposes browser-fetchable public feed URLs', () => {
    expect(MAPS_PUBLIC_FEEDS.earthquakes).toContain('earthquake.usgs.gov');
    expect(MAPS_PUBLIC_FEEDS.naturalEarth).toContain('natural-earth-vector');
    expect(MAPS_PUBLIC_FEEDS.wildfires).toContain('eonet.gsfc.nasa.gov');
    expect(MAPS_PUBLIC_FEEDS.eonet).toContain('status=open');
    expect(MAPS_PUBLIC_FEEDS.volcanoes).toContain('category=volcanoes');
    expect(MAPS_PUBLIC_FEEDS.firmsWms).toContain('firms.modaps.eosdis.nasa.gov');
    expect(MAPS_PUBLIC_FEEDS.temperature).toContain('open-meteo.com');
    expect(MAPS_PUBLIC_FEEDS.nhc).toContain('nhc.noaa.gov');
  });

  it('registers proxy routes for CORS / UA feeds', () => {
    expect(MAPS_PROXY_ROUTES.gdacs).toBe('/api/maps/gdacs');
    expect(MAPS_PROXY_ROUTES.nws).toBe('/api/maps/nws');
    expect(MAPS_PROXY_ROUTES.flights).toBe('/api/maps/flights');
    expect(MAPS_PROXY_ROUTES.news).toBe('/api/maps/news');
    expect(MAPS_PROXY_ROUTES.ais).toBe('/api/maps/ais');
    expect(MAPS_PROXY_ROUTES.openaq).toBe('/api/maps/openaq');
    expect(MAPS_PROXY_ROUTES.nhc).toBe('/api/maps/nhc');
    expect(MAPS_PROXY_ROUTES.iss).toBe('/api/maps/iss');
  });

  it('marks proxied Public datasets with proxy: true', () => {
    const proxied = getMapsDatasetsByCategory('public')
      .filter((d) => d.proxy)
      .map((d) => d.id);
    expect(proxied).toEqual([
      'gdacs',
      'openaq',
      'nws',
      'nhc',
      'flights',
      'news',
      'ais',
      'iss',
    ]);
  });

  it('registers every dataset id', () => {
    for (const dataset of MAPS_DATASETS) {
      expect(isMapsDatasetId(dataset.id)).toBe(true);
    }
    expect(isMapsDatasetId('not-a-dataset')).toBe(false);
  });

  it('ports WSR static conflict OSINT list (20 sites)', () => {
    expect(CONFLICT_SITES).toHaveLength(20);
    expect(CONFLICT_SITES.every((s) => Number.isFinite(s.lat))).toBe(true);
    expect(getMapsDataset('conflict')?.category).toBe('public');
  });
});
