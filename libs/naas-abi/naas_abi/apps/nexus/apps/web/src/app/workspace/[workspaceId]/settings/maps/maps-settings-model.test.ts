import { describe, expect, it } from 'vitest';
import type { WorkspaceFeedLayer } from '@/app/workspace/[workspaceId]/maps/lib/layouts';
import type { FeedVisibilityRow } from '@/app/workspace/[workspaceId]/maps/lib/maps-feed-visibility';
import type { MapsAccessItem } from '@/app/workspace/[workspaceId]/maps/lib/permissions-api';
import {
  feedCellValues,
  feedExportRow,
  feedSearchTexts,
  feedSortValue,
  layerCellValues,
  layerSearchTexts,
  layerSortValue,
  mapsAccessText,
  mapsFeedEntries,
  mapsLayerEntries,
} from './maps-settings-model';

const feedRow = (over: Partial<FeedVisibilityRow> & Pick<FeedVisibilityRow, 'id' | 'group'>): FeedVisibilityRow => ({
  title: over.id,
  source: 'SPARQL feed',
  layers: 1,
  shown: true,
  ...over,
});

const access = (over: Partial<MapsAccessItem> & Pick<MapsAccessItem, 'item_id'>): MapsAccessItem => ({
  kind: 'layout',
  title: over.item_id,
  owner: 'ws-1',
  editable: true,
  all_workspaces: false,
  workspace_ids: ['ws-1'],
  ...over,
});

const NAMES = new Map([
  ['ws-1', 'Alpha'],
  ['ws-2', 'Beta'],
]);

describe('the Access cell', () => {
  it('reads as the access editor shows it', () => {
    expect(mapsAccessText(undefined, NAMES)).toBe('—');
    expect(mapsAccessText(access({ item_id: 'a' }), NAMES)).toBe('This workspace only');
    expect(mapsAccessText(access({ item_id: 'a', editable: false, owner: 'ws-2' }), NAMES)).toBe('Shared from Beta');
    expect(mapsAccessText(access({ item_id: 'a', owner: '', all_workspaces: true }), NAMES)).toBe('All workspaces');
  });
});

describe('the Feed Layers table', () => {
  const ports = feedRow({ id: 'ports', group: 'Places', layers: 3 });
  const env = feedRow({ id: 'env', group: 'Environment', source: 'Built-in', shown: false });
  const roads = feedRow({ id: 'roads', group: 'Custom' });
  const gone = access({ item_id: 'gone', owner: '', workspace_ids: [] });
  const entries = mapsFeedEntries({
    rows: [ports, env, roads],
    unavailable: [gone],
    feedIds: new Set(['ports', 'roads']),
    canEdit: true,
    find: (id) => (id === 'ports' ? access({ item_id: 'ports', workspace_ids: ['ws-1', 'ws-2'] }) : undefined),
    names: NAMES,
  });
  const [p, e, r, u] = entries;

  it('keeps the groups in their listed order, unavailable feeds last', () => {
    expect(entries.map((entry) => feedSortValue(entry, 'group'))).toEqual([0, 1, 2, 3]);
    expect(feedSortValue(u!, 'layers')).toBe(-1);
    expect(feedSortValue(p!, 'layers')).toBe(3);
  });

  it('filters on group, layers, access and enabled: an unavailable feed is disabled and in no group', () => {
    expect(feedCellValues(p!, 'access')).toEqual(['Shared with Beta']);
    expect(feedCellValues(e!, 'access')).toEqual(['All workspaces']);
    expect(feedCellValues(r!, 'access')).toEqual(['—']);
    expect(feedCellValues(e!, 'enabled')).toEqual(['Disabled']);
    expect(feedCellValues(u!, 'group')).toEqual(['No group']);
    expect(feedCellValues(u!, 'enabled')).toEqual(['Disabled']);
    expect(feedCellValues(u!, 'access')).toEqual(['No workspace']);
    expect(feedCellValues(u!, 'layers')).toEqual(['—']);
  });

  it('without the right to edit, a feed of the workspace shows no access', () => {
    const [own] = mapsFeedEntries({
      rows: [ports],
      unavailable: [],
      feedIds: new Set(['ports']),
      canEdit: false,
      find: () => access({ item_id: 'ports' }),
      names: NAMES,
    });
    expect(own!.access).toBe('—');
  });

  it('searches the name, id, group and source; exports a row as shown', () => {
    expect(feedSearchTexts(e!)).toEqual(['env', 'env', 'Environment', 'Built-in']);
    expect(feedExportRow(p!)).toEqual(['ports', 'ports', 'Places', 'SPARQL feed', '3', 'Shared with Beta', 'Yes']);
    expect(feedExportRow(u!)).toEqual(['gone', 'gone', '', 'Not available in this workspace', '', 'No workspace', 'No']);
  });
});

describe("a feed's Layers table", () => {
  const layer = (over: Partial<WorkspaceFeedLayer> & Pick<WorkspaceFeedLayer, 'id' | 'title' | 'order'>) =>
    ({ feed_id: 'f', description: '', color: '#123456', icon: '', class_labels: [], ...over }) as WorkspaceFeedLayer;
  const rows = mapsLayerEntries(
    [
      layer({ id: 'b', title: 'Bridges', order: 2, class_labels: ['Bridge'] }),
      layer({ id: 'a', title: 'All', order: 2 }),
      layer({ id: 'p', title: 'Ports', order: 1, system: true }),
    ],
    ['b'],
  );

  it('orders by order then title, and knows which are hidden', () => {
    expect(rows.map((row) => row.id)).toEqual(['p', 'a', 'b']);
    expect(rows.map((row) => layerCellValues(row, 'shown')[0])).toEqual(['Shown', 'Shown', 'Hidden']);
    expect(layerSortValue(rows[0]!, 'order')).toBe(1);
  });

  it('filters feature types, Every feature for none; searches seeded layers', () => {
    expect(layerCellValues(rows[1]!, 'types')).toEqual(['Every feature']);
    expect(layerCellValues(rows[2]!, 'types')).toEqual(['Bridge']);
    expect(layerSearchTexts(rows[0]!)).toContain('seeded');
  });
});
