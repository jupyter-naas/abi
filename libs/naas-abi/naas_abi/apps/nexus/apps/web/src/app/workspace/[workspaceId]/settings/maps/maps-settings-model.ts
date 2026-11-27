/**
 * Settings › Maps, laid out as Settings › Users: the Feed Layers table (one row per feed, and per
 * deployment feed this workspace may not use) and a feed's Layers table, with their columns
 * (search, sort, filter, export). Pure: the view is `page.tsx`.
 */
import type { SettingsColumn } from '@/components/settings/users-table/settings-table';
import type { WorkspaceFeedLayer } from '@/app/workspace/[workspaceId]/maps/lib/layouts';
import type { FeedSource, FeedVisibilityRow } from '@/app/workspace/[workspaceId]/maps/lib/maps-feed-visibility';
import { accessSummary, type MapsAccessItem } from '@/app/workspace/[workspaceId]/maps/lib/permissions-api';

/** The Access cell as `MapsAccessCell` shows it, '—' while it is not known. */
export function mapsAccessText(item: MapsAccessItem | undefined, names: ReadonlyMap<string, string>): string {
  if (!item) return '—';
  if (!item.editable && item.owner) return `Shared from ${names.get(item.owner) ?? item.owner}`;
  return accessSummary(item, names);
}

/** A row of Feed Layers: a feed of the workspace, or a deployment feed it may not use. */
export type MapsFeedEntry = {
  id: string;
  title: string;
  /** '' for a feed this workspace may not use. */
  group: string;
  /** Where its group comes in the list (Custom last); unavailable feeds after every group. */
  groupRank: number;
  source: FeedSource;
  /** null for a feed this workspace may not use. */
  layers: number | null;
  shown: boolean;
  access: string;
  row: FeedVisibilityRow | null;
  unavailable: MapsAccessItem | null;
};

export function mapsFeedEntries({
  rows,
  unavailable,
  feedIds,
  canEdit,
  find,
  names,
}: {
  /** Feeds in their listed order: by group (Custom last), then by title. */
  rows: readonly FeedVisibilityRow[];
  unavailable: readonly MapsAccessItem[];
  /** Feeds with a record in this workspace (the others are built into Maps). */
  feedIds: ReadonlySet<string>;
  canEdit: boolean;
  find: (itemId: string) => MapsAccessItem | undefined;
  names: ReadonlyMap<string, string>;
}): MapsFeedEntry[] {
  const groups = [...new Set(rows.map((row) => row.group))];
  return [
    ...rows.map((row) => ({
      id: row.id,
      title: row.title,
      group: row.group,
      groupRank: groups.indexOf(row.group),
      source: row.source,
      layers: row.layers,
      shown: row.shown,
      access: !feedIds.has(row.id) ? 'All workspaces' : canEdit ? mapsAccessText(find(row.id), names) : '—',
      row,
      unavailable: null,
    })),
    ...unavailable.map((item) => ({
      id: item.item_id,
      title: item.title,
      group: '',
      groupRank: groups.length,
      source: 'API feed' as FeedSource,
      layers: null,
      shown: false,
      access: mapsAccessText(item, names),
      row: null,
      unavailable: item,
    })),
  ];
}

export type FeedColumnId = 'name' | 'group' | 'layers' | 'access' | 'enabled';
export const FEED_COLUMNS: SettingsColumn<FeedColumnId>[] = [
  { id: 'name', label: 'Name' },
  { id: 'group', label: 'Group', className: 'w-44' },
  { id: 'layers', label: 'Layers', className: 'w-24' },
  { id: 'access', label: 'Access', className: 'w-44' },
  { id: 'enabled', label: 'Enabled', className: 'w-28' },
];

export const NO_GROUP = 'No group';

/** What a column filter sees of a row: unavailable feeds are disabled and in no group. */
export function feedCellValues(entry: MapsFeedEntry, column: FeedColumnId): string[] {
  if (column === 'name') return [entry.title];
  if (column === 'group') return [entry.group || NO_GROUP];
  if (column === 'layers') return [entry.layers === null ? '—' : String(entry.layers)];
  if (column === 'access') return [entry.access];
  return [entry.shown ? 'Enabled' : 'Disabled'];
}

/** Groups in their listed order, layers as numbers. */
export function feedSortValue(entry: MapsFeedEntry, column: FeedColumnId): string | number {
  if (column === 'group') return entry.groupRank;
  if (column === 'layers') return entry.layers ?? -1;
  return feedCellValues(entry, column).join(', ');
}

/** What the search bar reads of a row: its name, id, group and source. */
export function feedSearchTexts(entry: MapsFeedEntry): string[] {
  return [entry.title, entry.id, entry.group, entry.source];
}

export const FEED_EXPORT_HEADERS = ['Name', 'Id', 'Group', 'Source', 'Layers', 'Access', 'Enabled'];

export function feedExportRow(entry: MapsFeedEntry): string[] {
  return [
    entry.title,
    entry.id,
    entry.group,
    entry.unavailable ? 'Not available in this workspace' : entry.source,
    entry.layers === null ? '' : String(entry.layers),
    entry.access,
    entry.shown ? 'Yes' : 'No',
  ];
}

/** A layer of a feed's Layers table, and whether it is shown in Maps. */
export type MapsLayerEntry = WorkspaceFeedLayer & { shown: boolean };

/** The layers by order, then title. */
export function mapsLayerEntries(layers: readonly WorkspaceFeedLayer[], hidden: readonly string[]): MapsLayerEntry[] {
  return [...layers]
    .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title))
    .map((layer) => ({ ...layer, shown: !hidden.includes(layer.id) }));
}

export type LayerColumnId = 'layer' | 'types' | 'order' | 'color' | 'shown';
export const LAYER_COLUMNS: SettingsColumn<LayerColumnId>[] = [
  { id: 'layer', label: 'Layer' },
  { id: 'types', label: 'Feature types' },
  { id: 'order', label: 'Order', className: 'w-24' },
  { id: 'color', label: 'Color', className: 'w-24' },
  { id: 'shown', label: 'Shown', className: 'w-24' },
];

export const EVERY_FEATURE = 'Every feature';

export function layerCellValues(layer: MapsLayerEntry, column: LayerColumnId): string[] {
  if (column === 'layer') return [layer.title];
  if (column === 'types') return layer.class_labels.length ? layer.class_labels : [EVERY_FEATURE];
  if (column === 'order') return [String(layer.order)];
  if (column === 'color') return [layer.color];
  return [layer.shown ? 'Shown' : 'Hidden'];
}

export function layerSortValue(layer: MapsLayerEntry, column: LayerColumnId): string | number {
  if (column === 'order') return layer.order;
  return layerCellValues(layer, column).join(', ');
}

export function layerSearchTexts(layer: MapsLayerEntry): string[] {
  return [layer.title, layer.id, ...layer.class_labels, layer.system ? 'seeded' : ''];
}
