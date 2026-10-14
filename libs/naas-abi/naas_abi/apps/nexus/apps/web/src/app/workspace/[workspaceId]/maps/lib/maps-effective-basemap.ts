import { getImportedMapLayer } from './maps-imported-layers';
import { getLayerDefaultBasemapId } from './maps-layer-basemap-prefs';
import { normalizeBasemapId, type MapsBasemapDef } from './maps-basemaps';
import type { LayoutEntry } from './layouts';

/** Basemap for the canvas: layer default when a single layer is active, else global choice. */
export function resolveMapsFeedBasemapId(options: {
  layerIds: string[];
  workspaceId: string;
  globalBasemapId: string;
  basemapDefs: readonly MapsBasemapDef[];
  /** Catalog default when nothing else applies. */
  defaultBasemapId?: string;
  /** Layer entries, for the default basemap stored on a layer record. */
  entries?: readonly Pick<LayoutEntry, 'id' | 'basemapId'>[];
}): string {
  const { layerIds, workspaceId, globalBasemapId, basemapDefs, defaultBasemapId, entries } = options;
  const normalize = (id: string) => normalizeBasemapId(id, basemapDefs, defaultBasemapId);
  if (layerIds.length === 1) {
    const layerId = layerIds[0];
    const pref = getLayerDefaultBasemapId(workspaceId, layerId);
    if (pref) return normalize(pref);

    const record = entries?.find((entry) => entry.id === layerId);
    if (record?.basemapId) return normalize(record.basemapId);

    const imported = getImportedMapLayer(workspaceId, layerId);
    if (imported?.defaultBasemapId) return normalize(imported.defaultBasemapId);
  }
  return normalize(globalBasemapId);
}
