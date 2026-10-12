/**
 * Maps data layers (UI: "layers"). Built-in feeds, module graph layers, and
 * workspace SPARQL layers from Settings → Maps.
 *
 * The API still calls workspace definitions "layouts"; this module is the
 * frontend layer list and visibility model.
 */
import type { CustomLayerGroup } from './maps-layer-groups';
import { layerGroupDefinitions } from './maps-layer-groups';
import { MAPS_CUSTOM_DATASETS } from '@/lib/maps-custom-datasets';
import type { MapsDataset, MapsLayerGroupId } from './datasets';
import {
  isMapsCategoryVisible,
  isMapsLayerGroupIdVisible,
  isMapsOrganizationFacilityOnlyDeployment,
} from './maps-deployment';

/** Reserved route for the combined map (`/maps/all`). */
export const ALL_LAYERS_ID = 'all';
/** @deprecated use ALL_LAYERS_ID */
export const ALL_LAYOUTS_ID = ALL_LAYERS_ID;

export type LayoutKind = 'builtin' | 'graph' | 'workspace' | 'imported';

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
  /** Workspace SPARQL layer color from Settings → Maps (optional). */
  color?: string;
}

/** On on All layers until a member toggles them off. */
const DEFAULT_ON_BUILTIN_IDS: ReadonlySet<string> = new Set([
  'gdacs',
  'volcanoes',
  'tropical-storms',
  'iss',
  'forvis-mazars-facilities',
  'valeo-facilities',
]);

function defaultOnLayerIds(): ReadonlySet<string> {
  if (isMapsOrganizationFacilityOnlyDeployment()) {
    return new Set(
      MAPS_CUSTOM_DATASETS.filter((d) => d.category === 'organizations-facility').map(
        (d) => d.id,
      ),
    );
  }
  return DEFAULT_ON_BUILTIN_IDS;
}

export function buildLayoutEntries(
  builtins: MapsDataset[],
  graphLayers: (MapsDataset & { graphUri: string })[],
  workspaceLayouts: WorkspaceMapLayout[],
  _options: {
    customIds?: ReadonlySet<string>;
    importedLayers?: ImportedLayerMeta[];
    workspaceLayerGroup?: (layoutId: string) => MapsLayerGroupId | undefined;
  } = {},
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
  for (const layer of graphLayers) {
    if (!isMapsCategoryVisible('custom')) continue;
    add({ ...layer, category: 'custom', kind: 'graph', combinable: true });
  }
  for (const layout of workspaceLayouts) {
    if (!isMapsCategoryVisible('custom')) continue;
    add({
      id: layout.id,
      title: layout.title,
      description: layout.description || 'Workspace layer (SPARQL)',
      icon: layout.icon || 'MapPin',
      category: _options.workspaceLayerGroup?.(layout.id) ?? 'custom',
      order: layout.order,
      kind: 'workspace',
      combinable: true,
      color: layout.color,
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
  return entry.kind !== 'builtin' || defaultOnLayerIds().has(entry.id);
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
