import { describe, expect, it } from 'vitest';

import type { MapsDataset } from './datasets';
import { buildLayoutEntries, type WorkspaceFeedLayer, type WorkspaceMapLayout } from './layouts';
import { feedVisibilityRows, type FeedVisibilityRow } from './maps-feed-visibility';

const ds = (id: string, group: string): MapsDataset => ({
  id, title: id[0].toUpperCase() + id.slice(1), description: '', group, icon: 'Map', order: 0,
});
const feed: WorkspaceMapLayout = {
  id: 'alpha', title: 'Alpha Org', description: '', icon: 'MapPin', color: '#2563eb', query: '', graphs: [],
  order: 1, feed_type: 'geojson_url', feed_url: '/api/x', group: 'Organizations Facilities',
};
const layer = (id: string): WorkspaceFeedLayer => ({
  id, feed_id: 'alpha', title: id, color: '#2563eb', icon: '', description: '', order: 1, class_labels: [],
  system: false, shared_from: '',
});

describe('feedVisibilityRows', () => {
  it('lists one row per feed with its layers, by group then title', () => {
    const entries = buildLayoutEntries(
      [ds('volcanoes', 'Environment'), ds('earthquakes', 'Environment'), ds('iss', 'SIGINT')],
      [],
      [feed],
      { feedLayers: [layer('alpha-offices'), layer('alpha-hq')] },
    );

    expect(feedVisibilityRows(entries, ['iss']).map((r) => [r.id, r.group, r.source, r.layers, r.shown])).toEqual([
      ['earthquakes', 'Environment', 'Built-in', 1, true],
      ['volcanoes', 'Environment', 'Built-in', 1, true],
      ['alpha', 'Organizations Facilities', 'API feed', 2, true],
      ['iss', 'SIGINT', 'Built-in', 1, false],
    ]);
  });

  it('leaves out browser-only imports', () => {
    const entries = buildLayoutEntries([], [], [], {
      importedLayers: [{ id: 'mine', title: 'Mine', description: '', icon: 'Layers', group: 'Custom', order: 0, color: '#000000' }],
    });
    expect(feedVisibilityRows(entries, [])).toEqual([]);
  });
});
