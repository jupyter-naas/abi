import { describe, expect, it } from 'vitest';

import {
  mapsDeploymentRestrictsLayerCatalog,
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
