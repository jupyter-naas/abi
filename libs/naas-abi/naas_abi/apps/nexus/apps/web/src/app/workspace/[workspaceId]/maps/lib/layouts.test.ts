import { describe, expect, it } from 'vitest';

import type { MapsDataset } from './datasets';
import {
  ALL_LAYERS_ID,
  buildLayoutEntries,
  groupLayerEntries,
  isLayerOn,
  visibleEntries,
  type WorkspaceMapLayout,
} from './layouts';

const ds = (id: string, category: MapsDataset['category'], order = 0): MapsDataset => ({
  id, title: id, description: '', category, icon: 'Map', order,
});
const workspaceLayer = (id: string): WorkspaceMapLayout => ({
  id, title: id.toUpperCase(), description: '', icon: 'MapPin', color: '#2563eb', query: '', graphs: [], order: 100,
});

describe('buildLayoutEntries', () => {
  it('merges built-in, graph and workspace layers, first id wins', () => {
    const entries = buildLayoutEntries(
      [ds('gdacs', 'public'), ds('earthquakes', 'public'), ds('presence', 'public')],
      [{ ...ds('kg-sites', 'custom'), graphUri: 'http://g' }, { ...ds('gdacs', 'custom'), graphUri: 'http://g' }],
      [workspaceLayer('offices'), workspaceLayer(ALL_LAYERS_ID)],
    );

    expect(entries.map((e) => [e.id, e.kind, e.combinable])).toEqual([
      ['gdacs', 'builtin', true],
      ['earthquakes', 'builtin', true],
      ['presence', 'builtin', true],
      ['kg-sites', 'graph', true],
      ['offices', 'workspace', true],
    ]);
    expect(entries.find((e) => e.id === 'offices')?.category).toBe('custom');
    expect(entries.find((e) => e.id === 'offices')?.color).toBe('#2563eb');
  });

  it('treats deployment Custom datasets as pin feeds', () => {
    const [entry] = buildLayoutEntries([ds('fleet', 'custom')], [], [], { customIds: new Set(['fleet']) });
    expect(entry.combinable).toBe(true);
  });
});

describe('isLayerOn', () => {
  const [gdacs, earthquakes, news] = buildLayoutEntries([ds('gdacs', 'public'), ds('earthquakes', 'public'), ds('news', 'public')], [], []);
  const [offices] = buildLayoutEntries([], [], [workspaceLayer('offices')]);

  it('defaults light built-ins and every workspace layer on', () => {
    expect(isLayerOn(gdacs, {})).toBe(true);
    expect(isLayerOn(news, {})).toBe(false);
    expect(isLayerOn(earthquakes, {})).toBe(false);
    expect(isLayerOn(offices, {})).toBe(true);
  });

  it('follows the member override', () => {
    expect(isLayerOn(gdacs, { gdacs: false })).toBe(false);
    expect(isLayerOn(news, { news: true })).toBe(true);
    expect(isLayerOn(earthquakes, { earthquakes: true })).toBe(true);
  });
});

describe('visibleEntries / groupLayerEntries', () => {
  const entries = buildLayoutEntries(
    [ds('volcanoes', 'public', 2), ds('gdacs', 'public', 1), ds('presence', 'public', 3)],
    [],
    [workspaceLayer('offices')],
  );

  it('drops hidden layers', () => {
    expect(visibleEntries(entries, ['gdacs', 'offices']).map((e) => e.id)).toEqual(['volcanoes', 'presence']);
  });

  it('groups Public then Custom, leaving empty groups out', () => {
    const groups = groupLayerEntries(visibleEntries(entries, ['presence']));
    expect(groups.map((g) => [g.id, g.entries.map((e) => e.id)])).toEqual([
      ['public', ['gdacs', 'volcanoes']],
      ['custom', ['offices']],
    ]);
  });
});
