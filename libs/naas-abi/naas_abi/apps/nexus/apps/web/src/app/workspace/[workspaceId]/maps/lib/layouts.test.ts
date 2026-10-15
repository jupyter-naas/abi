import { describe, expect, it } from 'vitest';

import type { MapsDataset } from './datasets';
import {
  ALL_LAYERS_ID,
  buildLayoutEntries,
  groupFeedLayers,
  compareLayerEntriesAsc,
  groupLayerEntries,
  defaultLayerOn,
  visibleEntries,
  type WorkspaceMapLayout,
} from './layouts';

const ds = (id: string, group: string, order = 0): MapsDataset => ({
  id, title: id, description: '', group, icon: 'Map', order,
});
const workspaceLayer = (id: string): WorkspaceMapLayout => ({
  id, title: id.toUpperCase(), description: '', icon: 'MapPin', color: '#2563eb', query: '', graphs: [], order: 100,
});

describe('buildLayoutEntries', () => {
  it('merges built-in, graph and workspace layers, first id wins', () => {
    const entries = buildLayoutEntries(
      [ds('gdacs', 'Environment'), ds('earthquakes', 'Environment'), ds('iss', 'SIGINT')],
      [{ ...ds('kg-sites', 'Custom'), graphUri: 'http://g' }, { ...ds('gdacs', 'Custom'), graphUri: 'http://g' }],
      [workspaceLayer('offices'), workspaceLayer(ALL_LAYERS_ID)],
    );

    expect(entries.map((e) => [e.id, e.kind, e.combinable])).toEqual([
      ['gdacs', 'builtin', true],
      ['earthquakes', 'builtin', true],
      ['iss', 'builtin', true],
      ['kg-sites', 'graph', true],
      ['offices', 'workspace', true],
    ]);
    expect(entries.find((e) => e.id === 'offices')?.group).toBe('Custom');
    expect(entries.find((e) => e.id === 'offices')?.color).toBe('#2563eb');
  });

  it('treats deployment Custom datasets as pin feeds', () => {
    const [entry] = buildLayoutEntries([ds('fleet', 'Custom')], [], [], { customIds: new Set(['fleet']) });
    expect(entry.combinable).toBe(true);
  });
});

describe('stored feeds (object storage)', () => {
  const key = 'intelligence/organizations/Acme/maps/acme.geojson';
  const feed: WorkspaceMapLayout = {
    ...workspaceLayer('acme'),
    feed_type: 'object_storage',
    logo_path: 'intelligence/organizations/Acme/logos/Acme.ico',
    logo_url: '/api/organizations/logos/Acme/Acme.ico',
  };
  const layers = [
    { id: 'acme', feed_id: 'acme', title: 'All', description: '', color: '#111111', icon: '', order: 1, class_labels: [], system: true, storage_path: key },
    { id: 'acme-hq', feed_id: 'acme', title: 'HQ', description: '', color: '#222222', icon: 'Landmark', order: 2, class_labels: ['Headquarters'], system: true, storage_path: key },
  ];

  it('makes one stored entry per layer with its object and the stored logo', () => {
    const entries = buildLayoutEntries([], [], [feed], {
      feedLayers: layers,
      logoUrls: { acme: 'blob:http://localhost/logo' },
    });
    expect(entries.map((e) => [e.id, e.kind, e.storagePath])).toEqual([
      ['acme', 'stored', key],
      ['acme-hq', 'stored', key],
    ]);
    // logo_path wins over logo_url; a layer with its own icon keeps it on pins.
    expect(entries[0].feedLogoUrl).toBe('blob:http://localhost/logo');
    expect(entries[0].layerLogoUrl).toBe('blob:http://localhost/logo');
    expect(entries[1].layerLogoUrl).toBeUndefined();
  });

  it('shows no logo until the stored logo is loaded', () => {
    const [entry] = buildLayoutEntries([], [], [feed], { feedLayers: layers.slice(0, 1) });
    expect(entry.feedLogoUrl).toBeUndefined();
  });
});

describe('defaultLayerOn', () => {
  const [gdacs, news] = buildLayoutEntries(
    [ds('gdacs', 'Environment'), ds('news', 'Situation')],
    [],
    [],
  );
  const [offices] = buildLayoutEntries([], [], [workspaceLayer('offices')]);

  it('defaults every enabled layer on (the workspace config decides which are enabled)', () => {
    expect(defaultLayerOn(gdacs)).toBe(true);
    expect(defaultLayerOn(news)).toBe(true);
    expect(defaultLayerOn(offices)).toBe(true);
  });
});

describe('compareLayerEntriesAsc', () => {
  it('sorts by title ascending', () => {
    expect(compareLayerEntriesAsc(ds('z', 'Environment'), ds('a', 'Environment'))).toBeGreaterThan(0);
    expect(
      [ds('iss', 'SIGINT'), ds('ais', 'SIGINT'), ds('flights', 'SIGINT')].sort(compareLayerEntriesAsc).map(
        (e) => e.id,
      ),
    ).toEqual(['ais', 'flights', 'iss']);
  });
});

describe('visibleEntries / groupLayerEntries', () => {
  const entries = buildLayoutEntries(
    [ds('volcanoes', 'Environment', 2), ds('gdacs', 'Environment', 1), ds('iss', 'SIGINT', 3)],
    [],
    [workspaceLayer('offices')],
  );

  it('drops hidden layers', () => {
    expect(visibleEntries(entries, ['gdacs', 'offices']).map((e) => e.id)).toEqual(['volcanoes', 'iss']);
  });

  it('drops every layer of a feed switched off, and built-ins are one-layer feeds', () => {
    expect(entries.find((e) => e.id === 'gdacs')).toMatchObject({ feedId: 'gdacs', feedTitle: 'gdacs' });
    expect(visibleEntries(entries, [], ['gdacs', 'offices']).map((e) => e.id)).toEqual(['volcanoes', 'iss']);
    expect(visibleEntries(entries, [], ['nothing']).length).toBe(entries.length);
  });

  it('groups by the entries\' labels, sorted, Custom last; empty groups omitted', () => {
    const groups = groupLayerEntries(visibleEntries(entries, ['iss']));
    expect(groups.map((g) => [g.id, g.label, g.entries.map((e) => e.id)])).toEqual([
      ['environment', 'Environment', ['gdacs', 'volcanoes']],
      ['custom', 'Custom', ['offices']],
    ]);
  });

  it('keeps every feed: any group label, a legacy category, or none', () => {
    const feeds = buildLayoutEntries([], [], [
      { ...workspaceLayer('a'), group: 'Field Offices' },
      { ...workspaceLayer('b'), category: 'public' },
      { ...workspaceLayer('c'), group: 'field offices' },
      { ...workspaceLayer('d'), category: 'not-a-known-slug' },
    ]);
    expect(groupLayerEntries(feeds).map((g) => [g.label, g.entries.map((e) => e.id)])).toEqual([
      ['Field Offices', ['a', 'c']],
      ['not-a-known-slug', ['d']],
      ['Public', ['b']],
    ]);
  });
});

describe('feed layers', () => {
  const energy = {
    id: 'energy',
    title: 'Energy Org',
    description: '',
    icon: 'Zap',
    color: '#001a70',
    query: '',
    graphs: [],
    order: 3,
    feed_type: 'geojson_url' as const,
    feed_url: '/api/maps/feeds/energy.geojson',
    group: 'Custom',
    logo_url: '/api/organizations/logos/Energy/Energy.ico',
  };
  const layer = (id: string, title: string, order: number, icon = '', class_labels: string[] = []) => ({
    id,
    feed_id: 'energy',
    title,
    description: '',
    color: '#e85130',
    icon,
    order,
    class_labels,
    system: true,
  });

  it('lists one entry per layer, carrying its feed', () => {
    const entries = buildLayoutEntries([], [], [energy], {
      feedLayers: [layer('energy-solar', 'Solar', 2, 'Sun', ['Solar']), layer('energy-all', 'All sites', 1)],
    });
    const solar = entries.find((e) => e.id === 'energy-solar')!;
    expect(solar).toMatchObject({
      kind: 'feed',
      feedId: 'energy',
      feedTitle: 'Energy Org',
      icon: 'Sun',
      ownIcon: true,
      classLabels: ['Solar'],
      layerLogoUrl: undefined,
    });
    // No own icon: the feed's logo.
    expect(entries.find((e) => e.id === 'energy-all')!.layerLogoUrl).toBe('/api/organizations/logos/Energy/Energy.ico');
  });

  it('falls back to one layer per feed with the feed id', () => {
    expect(buildLayoutEntries([], [], [energy]).map((e) => [e.id, e.feedId])).toEqual([['energy', 'energy']]);
  });

  it('groups a feed with several layers into one sidebar row', () => {
    const entries = buildLayoutEntries([], [], [energy], {
      feedLayers: [layer('energy-solar', 'Solar', 2), layer('energy-wind', 'Wind', 1)],
    });
    const items = groupFeedLayers(entries);
    expect(items).toHaveLength(1);
    const [feed] = items;
    expect(feed?.type).toBe('feed');
    if (feed?.type === 'feed') expect(feed.layers.map((l) => l.id)).toEqual(['energy-wind', 'energy-solar']);
    // One layer: a plain row.
    expect(groupFeedLayers(buildLayoutEntries([], [], [energy]))[0]?.type).toBe('layer');
  });
});
