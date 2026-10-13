import { describe, expect, it, vi } from 'vitest';

import {
  mapsDefaultOnFeedIds,
  mapsDeploymentRestrictsLayerCatalog,
  parseMapsDefaultOnFeedIds,
  parseMapsVisibleCategories,
} from './maps-deployment';

describe('parseMapsVisibleCategories', () => {
  it('returns null when unset', () => {
    expect(parseMapsVisibleCategories(undefined)).toBeNull();
    expect(parseMapsVisibleCategories('')).toBeNull();
  });

  it('parses a single group', () => {
    expect(parseMapsVisibleCategories('organizations-facility')).toEqual([
      'organizations-facility',
    ]);
  });

  it('drops unknown groups', () => {
    expect(parseMapsVisibleCategories('environment,not-a-group')).toEqual(['environment']);
  });
});

describe('parseMapsDefaultOnFeedIds', () => {
  it('parses comma-separated feed ids', () => {
    expect(parseMapsDefaultOnFeedIds('alpha-facilities, beta-facilities')).toEqual(
      new Set(['alpha-facilities', 'beta-facilities']),
    );
  });
});

describe('mapsDefaultOnFeedIds', () => {
  it('returns env feeds when set', async () => {
    vi.stubEnv('NEXT_PUBLIC_MAPS_DEFAULT_ON_FEED_IDS', 'alpha-facilities,beta-facilities');
    vi.resetModules();
    const { mapsDefaultOnFeedIds } = await import('./maps-deployment');
    expect(mapsDefaultOnFeedIds()).toEqual(new Set(['alpha-facilities', 'beta-facilities']));
    vi.unstubAllEnvs();
  });

  it('returns empty when env unset', async () => {
    vi.stubEnv('NEXT_PUBLIC_MAPS_DEFAULT_ON_FEED_IDS', '');
    vi.resetModules();
    const { mapsDefaultOnFeedIds } = await import('./maps-deployment');
    expect(mapsDefaultOnFeedIds()).toEqual(new Set());
    vi.unstubAllEnvs();
  });
});

describe('mapsDeploymentRestrictsLayerCatalog', () => {
  const key = 'NEXT_PUBLIC_MAPS_RESTRICT_LAYER_CATALOG';

  it('is false unless explicitly enabled', () => {
    const prev = process.env[key];
    delete process.env[key];
    expect(mapsDeploymentRestrictsLayerCatalog()).toBe(false);
    process.env[key] = 'true';
    expect(mapsDeploymentRestrictsLayerCatalog()).toBe(true);
    if (prev === undefined) delete process.env[key];
    else process.env[key] = prev;
  });
});
