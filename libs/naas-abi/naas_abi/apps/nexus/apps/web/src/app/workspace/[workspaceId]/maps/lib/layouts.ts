/**
 * Maps layouts: every layer the Maps section offers, whatever it comes from.
 *
 * - builtin: drawn by the web app (MAPS_DATASETS, incl. deployment Custom ones)
 * - graph:   registered by a module (GET /api/maps/layers)
 * - workspace: a SPARQL layout created in Settings → Maps
 *
 * A workspace admin can hide any layout (Settings → Maps). Each member then
 * switches layouts on or off for the "All layouts" map (per browser, like the
 * Search sidebar). Only layouts that produce pins can join that map; the
 * others (Earthquakes, Wildfires…) draw their own canvas and open on their own.
 */
import type { MapsDataset, MapsDatasetCategory } from './datasets';
import { MAPS_CATEGORIES } from './datasets';

/** Reserved route segment for the combined map: no layout can use it. */
export const ALL_LAYOUTS_ID = 'all';

export type LayoutKind = 'builtin' | 'graph' | 'workspace';

/** A layout created in Settings → Maps (the API's MapsLayout). */
export interface WorkspaceMapLayout {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  query: string;
  graphs: string[];
  order: number;
}

export interface LayoutEntry extends MapsDataset {
  kind: LayoutKind;
  /** Produces pins, so it can be overlaid on the All layouts map. */
  combinable: boolean;
  /** Graph layers: the graph the module projects. */
  graphUri?: string;
}

/** Built-in layouts whose canvas is a pin feed (MapsFeedCanvas), so they combine. */
export const COMBINABLE_BUILTIN_IDS: ReadonlySet<string> = new Set([
  'ais', 'conflict', 'eonet-all', 'flights', 'gdacs', 'gulf-strikes',
  'iss', 'news', 'nws-alerts', 'openaq', 'tropical-storms', 'volcanoes',
]);

/** On in All layouts until a member says otherwise: light, global feeds. */
const DEFAULT_ON_BUILTIN_IDS: ReadonlySet<string> = new Set(['gdacs', 'volcanoes', 'tropical-storms', 'iss']);

export function buildLayoutEntries(
  builtins: MapsDataset[],
  graphLayers: (MapsDataset & { graphUri: string })[],
  workspaceLayouts: WorkspaceMapLayout[],
  options: { customIds?: ReadonlySet<string> } = {},
): LayoutEntry[] {
  const taken = new Set<string>([ALL_LAYOUTS_ID]);
  const entries: LayoutEntry[] = [];
  const add = (entry: LayoutEntry) => {
    if (taken.has(entry.id)) return;
    taken.add(entry.id);
    entries.push(entry);
  };
  for (const dataset of builtins) {
    // Deployment Custom datasets are pin feeds by contract (MapsCustomFeed).
    const combinable = COMBINABLE_BUILTIN_IDS.has(dataset.id) || Boolean(options.customIds?.has(dataset.id));
    add({ ...dataset, kind: 'builtin', combinable });
  }
  for (const layer of graphLayers) add({ ...layer, category: 'custom', kind: 'graph', combinable: true });
  for (const layout of workspaceLayouts) {
    add({
      id: layout.id,
      title: layout.title,
      description: layout.description || 'Workspace layout (SPARQL)',
      icon: layout.icon || 'MapPin',
      category: 'custom',
      order: layout.order,
      kind: 'workspace',
      combinable: true,
    });
  }
  return entries;
}

export function visibleEntries(entries: LayoutEntry[], hidden: ReadonlySet<string> | string[]): LayoutEntry[] {
  const set = hidden instanceof Set ? hidden : new Set(hidden);
  return entries.filter((entry) => !set.has(entry.id));
}

/** Whether a layout is on the All layouts map. Non-combinable ones never are. */
export function isLayoutOn(entry: LayoutEntry, overrides: Record<string, boolean>): boolean {
  if (!entry.combinable) return false;
  if (entry.id in overrides) return overrides[entry.id];
  return entry.kind !== 'builtin' || DEFAULT_ON_BUILTIN_IDS.has(entry.id);
}

export interface LayoutGroup {
  id: MapsDatasetCategory;
  label: string;
  entries: LayoutEntry[];
}

/** Public / Private / Custom, each sorted; empty groups left out. */
export function groupLayoutEntries(entries: LayoutEntry[]): LayoutGroup[] {
  return MAPS_CATEGORIES.map(({ id, label }) => ({
    id,
    label,
    entries: entries
      .filter((entry) => entry.category === id)
      .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title)),
  })).filter((group) => group.entries.length > 0);
}
