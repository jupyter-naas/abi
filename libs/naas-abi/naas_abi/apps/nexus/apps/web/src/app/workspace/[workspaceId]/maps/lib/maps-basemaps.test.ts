import { describe, expect, it } from 'vitest';

import type { WorkspaceBasemap } from './basemaps-api';
import {
  FALLBACK_BASEMAP_ID,
  basemapDefFromApi,
  basemapLabel,
  normalizeBasemapId,
  splitBasemapPickerDefs,
  type MapsBasemapDef,
} from './maps-basemaps';

function api(overrides: Partial<WorkspaceBasemap> & Pick<WorkspaceBasemap, 'id'>): WorkspaceBasemap {
  return {
    title: overrides.id,
    category: 'standard',
    order: 100,
    renderer: { kind: 'countries' },
    system: true,
    preview_content_type: 'image/png',
    preview_version: 1,
    ...overrides,
  };
}

const CATALOG: MapsBasemapDef[] = [
  api({ id: 'topo', title: 'Topo', order: 40 }),
  api({ id: 'openstreetmap', title: 'Street', order: 10 }),
  api({ id: 'group', title: 'Group', category: 'organization' }),
  api({ id: 'emea', title: 'EMEA', category: 'custom', system: false, preview_content_type: null }),
].map(basemapDefFromApi);

describe('basemapDefFromApi', () => {
  it('maps API fields and drops the preview version when there is no preview', () => {
    const emea = CATALOG.find((def) => def.id === 'emea')!;
    expect(emea).toMatchObject({ label: 'EMEA', category: 'custom', system: false, previewVersion: 0 });
    expect(CATALOG.find((def) => def.id === 'group')!.previewVersion).toBe(1);
  });
});

describe('normalizeBasemapId', () => {
  it('keeps known ids', () => {
    expect(normalizeBasemapId('group', CATALOG)).toBe('group');
  });

  it('falls back to the catalog default, then the first basemap', () => {
    expect(normalizeBasemapId('gone', CATALOG)).toBe(FALLBACK_BASEMAP_ID);
    expect(normalizeBasemapId('gone', CATALOG, 'emea')).toBe('emea');
    const withoutDefault = CATALOG.filter((def) => def.id !== FALLBACK_BASEMAP_ID);
    expect(normalizeBasemapId('gone', withoutDefault)).toBe('topo');
  });

  it('keeps a stored id while the catalog is still loading', () => {
    expect(normalizeBasemapId('group', [])).toBe('group');
    expect(normalizeBasemapId(null, [])).toBe(FALLBACK_BASEMAP_ID);
  });
});

describe('splitBasemapPickerDefs', () => {
  it('splits by category and sorts each column by order', () => {
    const { standard, organization, custom } = splitBasemapPickerDefs(CATALOG);
    expect(standard.map((d) => d.id)).toEqual(['openstreetmap', 'topo']);
    expect(organization.map((d) => d.id)).toEqual(['group']);
    expect(custom.map((d) => d.id)).toEqual(['emea']);
  });

  it('omits hidden basemaps (not passed in)', () => {
    const { organization } = splitBasemapPickerDefs(CATALOG.filter((d) => d.id !== 'group'));
    expect(organization).toEqual([]);
  });
});

describe('basemapLabel', () => {
  it('uses the catalog name', () => {
    expect(basemapLabel('group', CATALOG)).toBe('Group');
    expect(basemapLabel('unknown', CATALOG)).toBe('Basemap');
  });
});
