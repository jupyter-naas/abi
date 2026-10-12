/**
 * Maps data layers (UI: "layers"). Built-in feeds, module graph layers, and
 * the workspace layer records from Settings → Maps: SPARQL layers and feed
 * layers (GeoJSON / pins from a Nexus API path, e.g. organization facilities).
 *
 * The API still calls workspace records "layouts"; this module is the
 * frontend layer list and visibility model.
 */
import type { CustomLayerGroup } from './maps-layer-groups';
import { layerGroupDefinitions } from './maps-layer-groups';
import type { MapsDataset, MapsLayerGroupId } from './datasets';
import { isMapsCategoryVisible, isMapsLayerGroupIdVisible } from './maps-deployment';
import { mapsPinImageUrl } from './maps-pin-image-url';

/** Reserved route for the combined map (`/maps/all`). */
export const ALL_LAYERS_ID = 'all';
/** @deprecated use ALL_LAYERS_ID */
export const ALL_LAYOUTS_ID = ALL_LAYERS_ID;

export type LayoutKind = 'builtin' | 'graph' | 'workspace' | 'feed' | 'imported';

export type LayoutFeedType = 'sparql' | 'geojson_url';

/** GeoJSON layer stored in the browser (File → New layer). */
export interface ImportedLayerMeta {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  order: number;
  groupId: MapsLayerGroupId;
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
  /** Sidebar group id (built-in category or custom). */
  category?: string;
  logo_url?: string;
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
  /** The layer has its own icon: drawn instead of the feed's logo on pins. */
  ownIcon?: boolean;
}

/** Built-in feeds on until a member toggles them off (layer records are always on). */
const DEFAULT_ON_BUILTIN_IDS: ReadonlySet<string> = new Set([
  'gdacs',
  'volcanoes',
  'tropical-storms',
  'iss',
]);

export function buildLayoutEntries(
  builtins: MapsDataset[],
  graphLayers: (MapsDataset & { graphUri: string })[],
  workspaceLayouts: WorkspaceMapLayout[],
  _options: {
    customIds?: ReadonlySet<string>;
    importedLayers?: ImportedLayerMeta[];
    workspaceLayerGroup?: (layoutId: string) => MapsLayerGroupId | undefined;
    /** Workspace colors for layers without a record (built-in, graph). */
    colors?: Readonly<Record<string, string>>;
    /** Layers of the feeds; when absent each feed is one layer (its default). */
    feedLayers?: readonly WorkspaceFeedLayer[];
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
  for (const dataset of builtins) {
    add({ ...dataset, kind: 'builtin', combinable: true, color: colors[dataset.id] });
  }
  for (const layer of graphLayers) {
    if (!isMapsCategoryVisible('custom')) continue;
    add({ ...layer, category: 'custom', kind: 'graph', combinable: true, color: colors[layer.id] });
  }
  // One entry per layer; each layer draws from a feed record (SPARQL or API feed).
  const feedsById = new Map(workspaceLayouts.map((feed) => [feed.id, feed]));
  const feedLayers = _options.feedLayers ?? workspaceLayouts.map(defaultFeedLayer);
  for (const layer of feedLayers) {
    const feed = feedsById.get(layer.feed_id);
    if (!feed) continue;
    const apiFeed = isFeedLayout(feed);
    const category = (
      apiFeed
        ? feed.category || 'custom'
        : _options.workspaceLayerGroup?.(feed.id) ?? feed.category ?? 'custom'
    ) as MapsLayerGroupId;
    if (!isMapsLayerGroupIdVisible(category)) continue;
    add({
      id: layer.id,
      title: layer.title,
      description:
        layer.description || feed.description || (apiFeed ? 'Feed layer' : 'Workspace layer (SPARQL)'),
      icon: layer.icon || feed.icon || 'MapPin',
      category,
      order: layer.order,
      kind: apiFeed ? 'feed' : 'workspace',
      combinable: true,
      color: layer.color,
      // A layer with its own icon shows it; otherwise the feed's logo.
      layerLogoUrl: layer.icon ? undefined : mapsPinImageUrl(feed.logo_url),
      basemapId: feed.basemap_id || undefined,
      metaLabel: feed.meta_label || undefined,
      system: layer.system,
      sharedFrom: layer.shared_from || feed.shared_from || undefined,
      feedId: feed.id,
      feedTitle: feed.title,
      feedLogoUrl: mapsPinImageUrl(feed.logo_url),
      feedColor: feed.color,
      classLabels: layer.class_labels,
      ownIcon: Boolean(layer.icon),
    });
  }
  for (const layer of _options.importedLayers ?? []) {
    const groupId = layer.groupId ?? 'custom';
    if (!isMapsLayerGroupIdVisible(groupId)) continue;
    add({
      id: layer.id,
      title: layer.title,
      description: layer.description || 'Imported GeoJSON (this browser)',
      icon: layer.icon || 'Layers',
      category: layer.groupId ?? 'custom',
      order: layer.order,
      kind: 'imported',
      combinable: true,
      color: layer.color,
    });
  }
  return entries;
}

export function visibleEntries(entries: LayoutEntry[], hidden: ReadonlySet<string> | string[]): LayoutEntry[] {
  const set = hidden instanceof Set ? hidden : new Set(hidden);
  return entries.filter((entry) => !set.has(entry.id));
}

/** Default on for a new session before the URL is seeded. */
export function defaultLayerOn(entry: LayoutEntry): boolean {
  if (!entry.combinable) return false;
  return entry.kind !== 'builtin' || DEFAULT_ON_BUILTIN_IDS.has(entry.id);
}

/** Whether a layer is drawn on the map (URL is preferred; overrides are legacy). */
export function isLayerOn(entry: LayoutEntry, overrides: Record<string, boolean>): boolean {
  if (!entry.combinable) return false;
  if (entry.id in overrides) return overrides[entry.id];
  return defaultLayerOn(entry);
}

/** @deprecated use isLayerOn */
export const isLayoutOn = isLayerOn;

export interface LayoutGroup {
  id: string;
  label: string;
  entries: LayoutEntry[];
}

export { layerGroupDefinitions };

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
 * the feed (Forvis Mazars › Offices). Other layers stay plain rows. Rows sort by title.
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

/** Built-in groups, then user-defined groups; empty groups omitted. */
export function groupLayerEntries(
  entries: LayoutEntry[],
  customGroups: ReadonlyArray<CustomLayerGroup> = [],
): LayoutGroup[] {
  return layerGroupDefinitions(customGroups)
    .map(({ id, label }) => ({
      id,
      label,
      entries: entries
        .filter((entry) => entry.category === id)
        .sort(compareLayerEntriesAsc),
    }))
    .filter((group) => group.entries.length > 0);
}

/** @deprecated use groupLayerEntries */
export const groupLayoutEntries = groupLayerEntries;
