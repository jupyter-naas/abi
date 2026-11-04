/**
 * Maps data layers (UI: "layers"). Built-in feeds, module graph layers, and
 * the workspace layer records from Settings → Maps: SPARQL layers and feed
 * layers (GeoJSON / pins from a Nexus API path, e.g. organization facilities).
 *
 * The API still calls workspace records "layouts"; this module is the
 * frontend layer list and visibility model.
 */
import type { MapsDataset } from './datasets';
import {
  DEFAULT_LAYER_GROUP,
  layerGroupKey,
  layerGroupLabels,
  layoutGroup,
} from './maps-layer-groups';
import { mapsPinImageUrl } from './maps-pin-image-url';

/** Reserved route for the combined map (`/maps/all`). */
export const ALL_LAYERS_ID = 'all';
/** @deprecated use ALL_LAYERS_ID */
export const ALL_LAYOUTS_ID = ALL_LAYERS_ID;

export type LayoutKind = 'builtin' | 'graph' | 'workspace' | 'feed' | 'stored' | 'imported';

export type LayoutFeedType = 'sparql' | 'geojson_url' | 'object_storage';

/** GeoJSON layer stored in the browser (File → New layer). */
export interface ImportedLayerMeta {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  order: number;
  group: string;
}

/** A layer record from Settings → Maps (the API's MapsLayout). */
export interface WorkspaceMapLayout {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  query: string;
  graphs: string[];
  order: number;
  /** Defaults to sparql when absent (older API responses). */
  feed_type?: LayoutFeedType;
  /** geojson_url: Nexus API path the web proxy fetches with the member's token. */
  feed_url?: string;
  /** Sidebar group label; feeds sharing it form one group. */
  group?: string;
  /** Pre-`group` slug from older API responses (read through layoutGroup). */
  category?: string;
  logo_url?: string;
  /** Logo in object storage, served by `/api/maps/layouts/{id}/logo` (wins over logo_url). */
  logo_path?: string;
  basemap_id?: string;
  meta_label?: string;
  fit_max_zoom?: number | null;
  /** Seeded by the deployment: editable and hideable, not deletable. */
  system?: boolean;
  /** Owning workspace when another workspace shares this record (read-only here). */
  shared_from?: string;
}

/** A layer drawn from a feed (the API's MapsFeedLayer); a feed has one at least. */
export interface WorkspaceFeedLayer {
  id: string;
  feed_id: string;
  title: string;
  description: string;
  color: string;
  /** Lucide key; empty = the feed's logo / icon. */
  icon: string;
  order: number;
  /** Feature types kept (pin classLabel); empty = every feature of the feed. */
  class_labels: string[];
  /** Stored feeds: object storage key of the layer's GeoJSON (`/feed-layers/{id}/data`). */
  storage_path?: string;
  system: boolean;
  shared_from?: string;
}

/** The layer a feed starts with (mirrors the API's default): every feature, the feed's look. */
export function defaultFeedLayer(feed: WorkspaceMapLayout): WorkspaceFeedLayer {
  return {
    id: feed.id,
    feed_id: feed.id,
    title: feed.title,
    description: feed.description,
    color: feed.color,
    icon: '',
    order: feed.order,
    class_labels: [],
    system: feed.system ?? false,
    shared_from: feed.shared_from,
  };
}

export function isFeedLayout(layout: Pick<WorkspaceMapLayout, 'feed_type'>): boolean {
  return layout.feed_type === 'geojson_url';
}

/** Feed whose layers each read a GeoJSON object from the platform's object storage. */
export function isStoredFeed(layout: Pick<WorkspaceMapLayout, 'feed_type'>): boolean {
  return layout.feed_type === 'object_storage';
}

/** Feeds with feature types (pin classLabel): API feeds and stored feeds. */
export function hasFeatureTypes(layout: Pick<WorkspaceMapLayout, 'feed_type'>): boolean {
  return isFeedLayout(layout) || isStoredFeed(layout);
}

export interface LayoutEntry extends MapsDataset {
  kind: LayoutKind;
  /** Pin layer that can stack on the All layers map. */
  combinable: boolean;
  /** Graph layers: the graph the module projects. */
  graphUri?: string;
  /** Default pin and group-by-country color from Settings → Maps (optional). */
  color?: string;
  /** Feed layers: default basemap when the layer is shown alone. */
  basemapId?: string;
  /** Feed layers: toolbar line, "{count}" replaced with the pin count. */
  metaLabel?: string;
  /** Seeded by the deployment (not deletable). */
  system?: boolean;
  /** Shared from another workspace (read-only here). */
  sharedFrom?: string;
  /** Layers drawn from a feed record: the feed they come from. */
  feedId?: string;
  feedTitle?: string;
  feedLogoUrl?: string;
  feedColor?: string;
  /** Feature types kept from the feed (pin classLabel); empty = all. */
  classLabels?: string[];
  /** Stored feeds: the layer's object storage key. */
  storagePath?: string;
  /** The layer has its own icon: drawn instead of the feed's logo on pins. */
  ownIcon?: boolean;
}

export function buildLayoutEntries(
  builtins: MapsDataset[],
  graphLayers: (MapsDataset & { graphUri: string })[],
  workspaceLayouts: WorkspaceMapLayout[],
  _options: {
    customIds?: ReadonlySet<string>;
    importedLayers?: ImportedLayerMeta[];
    /** Workspace colors for layers without a record (built-in, graph). */
    colors?: Readonly<Record<string, string>>;
    /** Layers of the feeds; when absent each feed is one layer (its default). */
    feedLayers?: readonly WorkspaceFeedLayer[];
    /** Object URLs of stored feed logos (`logo_path`), by feed id, once loaded. */
    logoUrls?: Readonly<Record<string, string>>;
  } = {},
): LayoutEntry[] {
  const colors = _options.colors ?? {};
  const taken = new Set<string>([ALL_LAYERS_ID]);
  const entries: LayoutEntry[] = [];
  const add = (entry: LayoutEntry) => {
    if (taken.has(entry.id)) return;
    taken.add(entry.id);
    entries.push(entry);
  };
  // Built-in and graph layers are one-layer feeds: the feed is the source, the
  // layer what is drawn (both share the id).
  for (const dataset of builtins) {
    add({
      ...dataset,
      kind: 'builtin',
      combinable: true,
      color: colors[dataset.id] ?? dataset.color,
      feedId: dataset.id,
      feedTitle: dataset.title,
    });
  }
  for (const layer of graphLayers) {
    add({
      ...layer,
      group: layer.group?.trim() || DEFAULT_LAYER_GROUP,
      kind: 'graph',
      combinable: true,
      // Workspace Settings → Maps wins; otherwise keep the catalog hex.
      color: colors[layer.id] ?? layer.color,
      feedId: layer.id,
      feedTitle: layer.title,
    });
  }
  // One entry per layer; each layer draws from a feed record (SPARQL or API feed).
  const feedsById = new Map(workspaceLayouts.map((feed) => [feed.id, feed]));
  const feedLayers = _options.feedLayers ?? workspaceLayouts.map(defaultFeedLayer);
  for (const layer of feedLayers) {
    const feed = feedsById.get(layer.feed_id);
    if (!feed) continue;
    const apiFeed = isFeedLayout(feed);
    const stored = isStoredFeed(feed);
    const feedLogo = feed.logo_path
      ? mapsPinImageUrl(_options.logoUrls?.[feed.id])
      : mapsPinImageUrl(feed.logo_url);
    add({
      id: layer.id,
      title: layer.title,
      description:
        layer.description
        || feed.description
        || (stored ? 'Stored layer' : apiFeed ? 'Feed layer' : 'Workspace layer (SPARQL)'),
      icon: layer.icon || feed.icon || 'MapPin',
      group: layoutGroup(feed),
      order: layer.order,
      kind: stored ? 'stored' : apiFeed ? 'feed' : 'workspace',
      combinable: true,
      color: layer.color,
      // A layer with its own icon shows it; otherwise the feed's logo.
      layerLogoUrl: layer.icon ? undefined : feedLogo,
      basemapId: feed.basemap_id || undefined,
      metaLabel: feed.meta_label || undefined,
      system: layer.system,
      sharedFrom: layer.shared_from || feed.shared_from || undefined,
      feedId: feed.id,
      feedTitle: feed.title,
      feedLogoUrl: feedLogo,
      feedColor: feed.color,
      classLabels: layer.class_labels,
      storagePath: stored ? layer.storage_path || undefined : undefined,
      ownIcon: Boolean(layer.icon),
    });
  }
  for (const layer of _options.importedLayers ?? []) {
    add({
      id: layer.id,
      title: layer.title,
      description: layer.description || 'Imported GeoJSON (this browser)',
      icon: layer.icon || 'Layers',
      group: layer.group.trim() || DEFAULT_LAYER_GROUP,
      order: layer.order,
      kind: 'imported',
      combinable: true,
      color: layer.color,
    });
  }
  return entries;
}

/** Entries not hidden: neither the layer itself nor the feed it is drawn from. */
export function visibleEntries(
  entries: LayoutEntry[],
  hidden: ReadonlySet<string> | string[],
  hiddenFeeds: ReadonlySet<string> | string[] = [],
): LayoutEntry[] {
  const set = hidden instanceof Set ? hidden : new Set(hidden);
  const feeds = hiddenFeeds instanceof Set ? hiddenFeeds : new Set(hiddenFeeds);
  return entries.filter((entry) => !set.has(entry.id) && !feeds.has(entry.feedId ?? entry.id));
}

/**
 * Default on for a new session before the URL is seeded: every enabled layer.
 * Which feeds are enabled is the workspace's `maps` config, then Settings → Maps.
 */
export function defaultLayerOn(entry: LayoutEntry): boolean {
  return entry.combinable;
}

export interface LayoutGroup {
  id: string;
  label: string;
  entries: LayoutEntry[];
}

/** Ascending title sort within a sidebar / legend group. */
export function compareLayerEntriesAsc(a: LayoutEntry, b: LayoutEntry): number {
  return a.title.localeCompare(b.title, undefined, { sensitivity: 'base' });
}

export type LayerGroupItem =
  | { type: 'layer'; entry: LayoutEntry }
  | { type: 'feed'; feedId: string; title: string; logoUrl?: string; layers: LayoutEntry[] };

/**
 * A sidebar group's rows: a feed becomes one feed row holding its layers (by
 * order, then title) when it has several, or one layer named differently from
 * the feed (org › Offices). Other layers stay plain rows. Rows sort by title.
 */
export function groupFeedLayers(entries: readonly LayoutEntry[]): LayerGroupItem[] {
  const byFeed = new Map<string, LayoutEntry[]>();
  for (const entry of entries) {
    if (entry.feedId) byFeed.set(entry.feedId, [...(byFeed.get(entry.feedId) ?? []), entry]);
  }
  const items: LayerGroupItem[] = [];
  const done = new Set<string>();
  for (const entry of entries) {
    const siblings = entry.feedId ? byFeed.get(entry.feedId) ?? [] : [];
    const ownName = siblings.length === 1 && entry.feedTitle !== undefined && entry.title !== entry.feedTitle;
    if (siblings.length === 0 || (siblings.length === 1 && !ownName)) {
      items.push({ type: 'layer', entry });
      continue;
    }
    if (done.has(entry.feedId!)) continue;
    done.add(entry.feedId!);
    items.push({
      type: 'feed',
      feedId: entry.feedId!,
      title: entry.feedTitle ?? entry.feedId!,
      logoUrl: entry.feedLogoUrl,
      layers: [...siblings].sort((a, b) => a.order - b.order || compareLayerEntriesAsc(a, b)),
    });
  }
  const titleOf = (item: LayerGroupItem) => (item.type === 'feed' ? item.title : item.entry.title);
  return items.sort((a, b) => titleOf(a).localeCompare(titleOf(b), undefined, { sensitivity: 'base' }));
}

/** One group per distinct `group` label on the entries (sorted, Custom last). */
export function groupLayerEntries(entries: LayoutEntry[]): LayoutGroup[] {
  const groupOf = (entry: LayoutEntry) => entry.group?.trim() || DEFAULT_LAYER_GROUP;
  return layerGroupLabels(entries.map(groupOf)).map((label) => {
    const key = layerGroupKey(label);
    return {
      id: key,
      label,
      entries: entries
        .filter((entry) => layerGroupKey(groupOf(entry)) === key)
        .sort(compareLayerEntriesAsc),
    };
  });
}

/** @deprecated use groupLayerEntries */
export const groupLayoutEntries = groupLayerEntries;
