/**
 * Maps routes use query parameters for active layers:
 *
 *   /workspace/{id}/maps
 *   /workspace/{id}/maps?layer=earthquakes&layer=temperature
 */

export interface MapsRoute {
  isMapsRoute: boolean;
  /** Layer ids from repeated `layer` query params (may include unknown ids). */
  layerIds: string[];
  /** Mobile map detail when at least one layer is selected. */
  isMapView: boolean;
  /** @deprecated use isMapView */
  isDataset: boolean;
  /** @deprecated use layerIds[0] */
  datasetId: string | null;
}

/** Workspace Maps app only — not Settings → Maps (`…/settings/maps`). */
const MAPS_SEGMENT = /\/maps(?=[/?#]|$)/;

function isWorkspaceMapsPath(pathname: string): boolean {
  if (pathname.includes('/settings/')) return false;
  return MAPS_SEGMENT.test(pathname);
}

export function parseMapsLayerIds(
  search: string | URLSearchParams | null | undefined,
): string[] {
  if (!search) return [];
  const params =
    typeof search === 'string'
      ? new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
      : search;
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const raw of params.getAll('layer')) {
    const id = raw.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
  }
  return ids;
}

export function parseMapsRoute(
  pathname: string | null | undefined,
  search?: string | URLSearchParams | null,
): MapsRoute {
  if (!pathname || !isWorkspaceMapsPath(pathname)) {
    return { isMapsRoute: false, layerIds: [], isMapView: false, isDataset: false, datasetId: null };
  }
  const layerIds = parseMapsLayerIds(search);
  const isMapView = layerIds.length > 0;
  return {
    isMapsRoute: true,
    layerIds,
    isMapView,
    isDataset: isMapView,
    datasetId: layerIds[0] ?? null,
  };
}

/** Path of the maps library / map shell for a workspace. */
export function mapsLibraryPath(workspaceId: string | null): string {
  return workspaceId ? `/workspace/${workspaceId}/maps` : '/maps';
}

/** Map URL with zero or more active layers. */
export function mapsPath(workspaceId: string | null, layerIds: readonly string[]): string {
  const base = mapsLibraryPath(workspaceId);
  const unique = [...new Set(layerIds.filter(Boolean))];
  if (!unique.length) return base;
  const qs = unique.map((id) => `layer=${encodeURIComponent(id)}`).join('&');
  return `${base}?${qs}`;
}

/** Single-layer map URL. */
export function mapsLayerPath(workspaceId: string | null, layerId: string): string {
  return mapsPath(workspaceId, [layerId]);
}

/** @deprecated use mapsLayerPath */
export function mapsDatasetPath(workspaceId: string | null, datasetId: string): string {
  return mapsLayerPath(workspaceId, datasetId);
}

/** @deprecated use mapsPath(workspaceId, layerIds) */
export function mapsAllLayersPath(workspaceId: string | null): string {
  return mapsLibraryPath(workspaceId);
}

/** @deprecated use mapsAllLayersPath */
export const mapsAllLayoutsPath = mapsAllLayersPath;

/** Settings → Maps, optionally on one layout or on a new blank one. */
export function mapsSettingsPath(
  workspaceId: string | null,
  options: { layout?: string; create?: boolean } = {},
): string {
  const base = workspaceId ? `/workspace/${encodeURIComponent(workspaceId)}/settings/maps` : '/settings/maps';
  if (options.create) return `${base}?layout=new`;
  return options.layout ? `${base}?layout=${encodeURIComponent(options.layout)}` : base;
}
