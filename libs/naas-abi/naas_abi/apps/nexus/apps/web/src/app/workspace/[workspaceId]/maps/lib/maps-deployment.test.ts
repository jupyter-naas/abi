import { describe, expect, it } from 'vitest';

import { mapsDeploymentRestrictsLayerCatalog } from './maps-deployment';

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
