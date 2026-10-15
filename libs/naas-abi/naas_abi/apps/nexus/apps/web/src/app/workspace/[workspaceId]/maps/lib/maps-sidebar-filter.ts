/**
 * Sidebar Groups / Feeds filters. An empty selection means "all"; the filters
 * only narrow what the sidebar lists, never which layers are on the map.
 */

import { groupLayerEntries, type LayoutEntry } from './layouts';
import { DEFAULT_LAYER_GROUP, layerGroupKey } from './maps-layer-groups';

export interface SidebarFilterOption {
  value: string;
  label: string;
  detail?: string;
}

export interface SidebarFilter {
  /** Group keys (`layerGroupKey`). */
  groups: readonly string[];
  /** Feed ids; a layer outside any feed is its own feed. */
  feeds: readonly string[];
}

/** The feed a sidebar entry belongs to (a plain layer is its own feed). */
export function entryFeedKey(entry: LayoutEntry): string {
  return entry.feedId ?? entry.id;
}

function entryGroupKey(entry: LayoutEntry): string {
  return layerGroupKey(entry.group?.trim() || DEFAULT_LAYER_GROUP);
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`;
}

export function sidebarGroupOptions(entries: LayoutEntry[]): SidebarFilterOption[] {
  return groupLayerEntries(entries).map((group) => ({
    value: group.id,
    label: group.label,
    detail: plural(new Set(group.entries.map(entryFeedKey)).size, 'feed'),
  }));
}

/** Feeds sorted by title, limited to the selected groups. */
export function sidebarFeedOptions(
  entries: LayoutEntry[],
  groups: readonly string[] = [],
): SidebarFilterOption[] {
  const feeds = new Map<string, { label: string; group: string; layers: number }>();
  for (const entry of entries) {
    if (groups.length && !groups.includes(entryGroupKey(entry))) continue;
    const key = entryFeedKey(entry);
    const feed = feeds.get(key);
    if (feed) feed.layers += 1;
    else {
      feeds.set(key, {
        label: entry.feedTitle?.trim() || entry.title,
        group: entry.group?.trim() || DEFAULT_LAYER_GROUP,
        layers: 1,
      });
    }
  }
  return [...feeds.entries()]
    .map(([value, feed]) => ({
      value,
      label: feed.label,
      detail: `${feed.group} · ${plural(feed.layers, 'layer')}`,
    }))
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

export function filterSidebarEntries(entries: LayoutEntry[], filter: SidebarFilter): LayoutEntry[] {
  if (!filter.groups.length && !filter.feeds.length) return entries;
  return entries.filter(
    (entry) =>
      (!filter.groups.length || filter.groups.includes(entryGroupKey(entry))) &&
      (!filter.feeds.length || filter.feeds.includes(entryFeedKey(entry))),
  );
}

/** Trigger label: "All groups", the one selected name, or "N groups selected". */
export function sidebarFilterLabel(
  value: readonly string[],
  options: readonly SidebarFilterOption[],
  noun: string,
): string {
  if (!value.length) return `All ${noun}`;
  if (value.length === 1) {
    return options.find((option) => option.value === value[0])?.label ?? `1 ${noun.replace(/s$/, '')} selected`;
  }
  return `${value.length} ${noun} selected`;
}

export function toggleValue(values: readonly string[], value: string): string[] {
  return values.includes(value) ? values.filter((v) => v !== value) : [...values, value];
}
