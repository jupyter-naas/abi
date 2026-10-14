/**
 * Settings → Maps feed visibility: one row per feed of the workspace (records,
 * built-ins and graph layers, which are one-layer feeds), switched on or off as
 * a whole. Browser-only imports are left out: they belong to one browser.
 */

import { groupLayerEntries, type LayoutEntry } from './layouts';

export type FeedSource = 'Built-in' | 'API feed' | 'Stored feed' | 'SPARQL feed' | 'Graph';

export interface FeedVisibilityRow {
  id: string;
  title: string;
  group: string;
  source: FeedSource;
  layers: number;
  /** The feed is on (not in `hidden_feeds`). */
  shown: boolean;
  logoUrl?: string;
}

const SOURCE: Partial<Record<LayoutEntry['kind'], FeedSource>> = {
  builtin: 'Built-in',
  feed: 'API feed',
  stored: 'Stored feed',
  workspace: 'SPARQL feed',
  graph: 'Graph',
};

/** Feeds by group (sorted, Custom last), then by title. */
export function feedVisibilityRows(
  entries: readonly LayoutEntry[],
  hiddenFeeds: readonly string[],
): FeedVisibilityRow[] {
  const off = new Set(hiddenFeeds);
  const rows: FeedVisibilityRow[] = [];
  for (const group of groupLayerEntries(entries.filter((entry) => SOURCE[entry.kind]))) {
    const byFeed = new Map<string, FeedVisibilityRow>();
    for (const entry of group.entries) {
      const id = entry.feedId ?? entry.id;
      const row = byFeed.get(id);
      if (row) {
        row.layers += 1;
        continue;
      }
      byFeed.set(id, {
        id,
        title: entry.feedTitle ?? entry.title,
        group: group.label,
        source: SOURCE[entry.kind]!,
        layers: 1,
        shown: !off.has(id),
        logoUrl: entry.feedLogoUrl ?? entry.layerLogoUrl,
      });
    }
    rows.push(
      ...[...byFeed.values()].sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: 'base' })),
    );
  }
  return rows;
}

export type FeedStatusFilter = 'all' | 'enabled' | 'disabled';

export interface FeedRowFilter {
  search: string;
  /** A group label, or 'all'. */
  group: string;
  status: FeedStatusFilter;
}

/** Rows matching the search (name, id, group, source) and the group / status filters. */
export function filterFeedRows<T extends Pick<FeedVisibilityRow, 'id' | 'title' | 'group' | 'source' | 'shown'>>(
  rows: readonly T[],
  filter: FeedRowFilter,
): T[] {
  const query = filter.search.trim().toLowerCase();
  const group = filter.group === 'all' ? null : filter.group.trim().toLowerCase();
  return rows.filter(
    (row) =>
      (!query || [row.title, row.id, row.group, row.source].some((text) => text.toLowerCase().includes(query)))
      && (!group || row.group.trim().toLowerCase() === group)
      && (filter.status === 'all' || row.shown === (filter.status === 'enabled')),
  );
}
