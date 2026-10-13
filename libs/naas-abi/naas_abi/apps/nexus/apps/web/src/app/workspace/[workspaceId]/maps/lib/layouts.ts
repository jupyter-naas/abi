/**
 * Maps data layers (UI: "layers"). Built-in feeds, module graph layers, and
 * workspace SPARQL layers from Settings → Maps.
 *
 * The API still calls workspace definitions "layouts"; this module is the
 * frontend layer list and visibility model.
 */
import type { MapsDataset, MapsDatasetCategory } from './datasets';
import { MAPS_CATEGORIES } from './datasets';

/** Reserved route for the combined map (`/maps/all`). */
export const ALL_LAYERS_ID = 'all';
/** @deprecated use ALL_LAYERS_ID */
export const ALL_LAYOUTS_ID = ALL_LAYERS_ID;

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
  /** Pin layer that can stack on the All layers map. */
  combinable: boolean;
  /** Graph layers: the graph the module projects. */
  graphUri?: string;
}

/** On on All layers until a member toggles them off. */
const DEFAULT_ON_BUILTIN_IDS: ReadonlySet<string> = new Set(['gdacs', 'volcanoes', 'tropical-storms', 'iss']);

export function buildLayoutEntries(
  builtins: MapsDataset[],
  graphLayers: (MapsDataset & { graphUri: string })[],
  workspaceLayouts: WorkspaceMapLayout[],
  _options: { customIds?: ReadonlySet<string> } = {},
): LayoutEntry[] {
  const taken = new Set<string>([ALL_LAYERS_ID]);
  const entries: LayoutEntry[] = [];
  const add = (entry: LayoutEntry) => {
    if (taken.has(entry.id)) return;
    taken.add(entry.id);
    entries.push(entry);
  };
  for (const dataset of builtins) {
    add({ ...dataset, kind: 'builtin', combinable: true });
  }
  for (const layer of graphLayers) add({ ...layer, category: 'custom', kind: 'graph', combinable: true });
  for (const layout of workspaceLayouts) {
    add({
      id: layout.id,
      title: layout.title,
      description: layout.description || 'Workspace layer (SPARQL)',
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

/** Whether a layer is drawn on the All layers map. */
export function isLayerOn(entry: LayoutEntry, overrides: Record<string, boolean>): boolean {
  if (!entry.combinable) return false;
  if (entry.id in overrides) return overrides[entry.id];
  return entry.kind !== 'builtin' || DEFAULT_ON_BUILTIN_IDS.has(entry.id);
}

/** @deprecated use isLayerOn */
export const isLayoutOn = isLayerOn;

export interface LayoutGroup {
  id: MapsDatasetCategory;
  label: string;
  entries: LayoutEntry[];
}

/** Public then Custom; empty groups omitted. */
export function groupLayerEntries(entries: LayoutEntry[]): LayoutGroup[] {
  return MAPS_CATEGORIES.map(({ id, label }) => ({
    id,
    label,
    entries: entries
      .filter((entry) => entry.category === id)
      .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title)),
  })).filter((group) => group.entries.length > 0);
}

/** @deprecated use groupLayerEntries */
export const groupLayoutEntries = groupLayerEntries;
