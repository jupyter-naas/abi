import { describe, expect, it } from 'vitest';

import {
  getMapsDataset,
  getMapsDatasetsByCategory,
  isMapsDatasetId,
  MAPS_DATASETS,
  MAPS_PUBLIC_FEEDS,
} from './datasets';

describe('MAPS_DATASETS taxonomy', () => {
  it('groups sources like Search: Public, Private, Custom', () => {
    expect(getMapsDatasetsByCategory('public').map((d) => d.id)).toEqual([
      'openstreetmap',
      'earthquakes',
      'natural-earth',
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

  it('exposes browser-fetchable public feed URLs from WSR', () => {
    expect(MAPS_PUBLIC_FEEDS.earthquakes).toContain('earthquake.usgs.gov');
    expect(MAPS_PUBLIC_FEEDS.naturalEarth).toContain('natural-earth-vector');
  });

  it('registers every dataset id', () => {
    for (const dataset of MAPS_DATASETS) {
      expect(isMapsDatasetId(dataset.id)).toBe(true);
    }
    expect(isMapsDatasetId('not-a-dataset')).toBe(false);
  });
});
