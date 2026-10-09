import { describe, expect, it } from 'vitest';

import type { MapsDataset } from './datasets';
import {
  ALL_LAYOUTS_ID,
  buildLayoutEntries,
  groupLayoutEntries,
  isLayoutOn,
  resolveBasemapId,
  visibleEntries,
  type WorkspaceMapLayout,
} from './layouts';

const ds = (id: string, category: MapsDataset['category'], order = 0): MapsDataset => ({
  id, title: id, description: '', category, icon: 'Map', order,
});
const layout = (id: string): WorkspaceMapLayout => ({
  id, title: id.toUpperCase(), description: '', icon: 'MapPin', color: '#2563eb', query: '', graphs: [], order: 100,
});

describe('buildLayoutEntries', () => {
  it('merges built-in, graph and workspace layouts, first id wins', () => {
    const entries = buildLayoutEntries(
      [ds('gdacs', 'public'), ds('earthquakes', 'public'), ds('openstreetmap', 'basemap'), ds('presence', 'public')],
      [{ ...ds('kg-sites', 'custom'), graphUri: 'http://g' }, { ...ds('gdacs', 'custom'), graphUri: 'http://g' }],
      [layout('offices'), layout(ALL_LAYOUTS_ID)],
    );

    expect(entries.map((e) => [e.id, e.kind, e.combinable])).toEqual([
      ['gdacs', 'builtin', true],
      ['earthquakes', 'builtin', true],
      ['openstreetmap', 'builtin', false],
      ['presence', 'builtin', true],
      ['kg-sites', 'graph', true],
      ['offices', 'workspace', true],
    ]);
    expect(entries.find((e) => e.id === 'offices')?.category).toBe('custom');
  });

  it('treats deployment Custom datasets as pin feeds', () => {
    const [entry] = buildLayoutEntries([ds('fleet', 'custom')], [], [], { customIds: new Set(['fleet']) });
    expect(entry.combinable).toBe(true);
  });
});

describe('isLayoutOn', () => {
  const [gdacs, earthquakes, news] = buildLayoutEntries([ds('gdacs', 'public'), ds('earthquakes', 'public'), ds('news', 'public')], [], []);
  const [osm] = buildLayoutEntries([ds('openstreetmap', 'basemap')], [], []);
  const [offices] = buildLayoutEntries([], [], [layout('offices')]);

  it('defaults light built-ins and every workspace layout on', () => {
    expect(isLayoutOn(gdacs, {})).toBe(true);
    expect(isLayoutOn(news, {})).toBe(false);
    expect(isLayoutOn(earthquakes, {})).toBe(false);
    expect(isLayoutOn(offices, {})).toBe(true);
  });

  it('follows the member override', () => {
    expect(isLayoutOn(gdacs, { gdacs: false })).toBe(false);
    expect(isLayoutOn(news, { news: true })).toBe(true);
    expect(isLayoutOn(earthquakes, { earthquakes: true })).toBe(true);
  });

  it('never draws a basemap as a stacked layout', () => {
    expect(isLayoutOn(osm, { openstreetmap: true })).toBe(false);
  });
});

describe('resolveBasemapId', () => {
  const entries = buildLayoutEntries(
    [ds('openstreetmap', 'basemap'), ds('natural-earth', 'basemap', 1), ds('gdacs', 'public')],
    [],
    [],
  );

  it('keeps a visible choice and falls back when it is hidden', () => {
    expect(resolveBasemapId(entries, 'natural-earth')).toBe('natural-earth');
    expect(resolveBasemapId(entries, 'missing')).toBe('openstreetmap');
    expect(resolveBasemapId(visibleEntries(entries, ['openstreetmap']), 'openstreetmap')).toBe('natural-earth');
  });
});

describe('visibleEntries / groupLayoutEntries', () => {
  const entries = buildLayoutEntries(
    [ds('openstreetmap', 'basemap', 0), ds('volcanoes', 'public', 2), ds('gdacs', 'public', 1), ds('presence', 'public', 3)],
    [],
    [layout('offices')],
  );

  it('drops hidden layouts', () => {
    expect(visibleEntries(entries, ['gdacs', 'offices']).map((e) => e.id)).toEqual(['openstreetmap', 'volcanoes', 'presence']);
  });

  it('groups basemap, then public, then custom, leaving empty groups out', () => {
    const groups = groupLayoutEntries(visibleEntries(entries, ['presence']));
    expect(groups.map((g) => [g.id, g.entries.map((e) => e.id)])).toEqual([
      ['basemap', ['openstreetmap']],
      ['public', ['gdacs', 'volcanoes']],
      ['custom', ['offices']],
    ]);
  });
});
