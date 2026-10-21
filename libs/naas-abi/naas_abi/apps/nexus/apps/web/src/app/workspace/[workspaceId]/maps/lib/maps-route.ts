/**
 * Maps routes use query parameters for active layers:
 *
 *   /workspace/{id}/maps
 *   /workspace/{id}/maps?layer=earthquakes&layer=temperature
 *   /workspace/{id}/maps?layer=          (every layer switched off)
 *
 * No `layer` param means the member has not chosen yet: the map applies the
 * default layers. An empty `layer=` keeps an explicit "none" from being undone.
 */

export interface MapsRoute {
  isMapsRoute: boolean;
  /** Layer ids from repeated `layer` query params (may include unknown ids). */
  layerIds: string[];
  /** Mobile map detail when at least one layer is selected. */
  isMapView: boolean;
}

/** Query string or search params (Next's read-only params included). */
type MapsSearch = string | Pick<URLSearchParams, 'getAll' | 'has'> | null | undefined;

function searchParamsOf(search: string | Pick<URLSearchParams, 'getAll' | 'has'>) {
  return typeof search === 'string'
    ? new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
    : search;
}

/** Workspace Maps app only — not Settings → Maps (`…/settings/maps`). */
const MAPS_SEGMENT = /\/maps(?=[/?#]|$)/;

function isWorkspaceMapsPath(pathname: string): boolean {
  if (pathname.includes('/settings/')) return false;
  return MAPS_SEGMENT.test(pathname);
}

export function parseMapsLayerIds(search: MapsSearch): string[] {
  if (!search) return [];
  const params = searchParamsOf(search);
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

/** Whether the URL carries a layer choice (possibly empty), as opposed to none yet. */
export function hasMapsLayerChoice(search: MapsSearch): boolean {
  return !!search && searchParamsOf(search).has('layer');
}

export function parseMapsRoute(
  pathname: string | null | undefined,
  search?: MapsSearch,
): MapsRoute {
  if (!pathname || !isWorkspaceMapsPath(pathname)) {
    return { isMapsRoute: false, layerIds: [], isMapView: false };
  }
  const layerIds = parseMapsLayerIds(search);
  return { isMapsRoute: true, layerIds, isMapView: layerIds.length > 0 };
}

/** Path of the maps library / map shell for a workspace. */
export function mapsLibraryPath(workspaceId: string | null): string {
  return workspaceId ? `/workspace/${workspaceId}/maps` : '/maps';
}

/**
 * Map URL with zero or more active layers. With `explicit`, no layers is kept
 * as `?layer=` so the defaults are not applied again.
 */
export function mapsPath(
  workspaceId: string | null,
  layerIds: readonly string[],
  options: { explicit?: boolean } = {},
): string {
  const base = mapsLibraryPath(workspaceId);
  const unique = [...new Set(layerIds.filter(Boolean))];
  if (!unique.length) return options.explicit ? `${base}?layer=` : base;
  const qs = unique.map((id) => `layer=${encodeURIComponent(id)}`).join('&');
  return `${base}?${qs}`;
}

/** Single-layer map URL. */
export function mapsLayerPath(workspaceId: string | null, layerId: string): string {
  return mapsPath(workspaceId, [layerId]);
}

/**
 * Settings → Maps: the overview, one feed (`?feed=`), one layer (`?layer=`), or
 * a new one (`new`; a new layer can start on a feed with `&for=`).
 */
export function mapsSettingsPath(
  workspaceId: string | null,
  options: { layer?: string; feed?: string; create?: boolean; forFeed?: string } = {},
): string {
  const base = workspaceId ? `/workspace/${encodeURIComponent(workspaceId)}/settings/maps` : '/settings/maps';
  const params = new URLSearchParams();
  if (options.feed) params.set('feed', options.feed);
  else if (options.create) params.set('layer', 'new');
  else if (options.layer) params.set('layer', options.layer);
  if (options.forFeed) params.set('for', options.forFeed);
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}

/** The feed selected in Settings → Maps (`?feed=`). */
export function mapsSettingsSelectedFeed(params: { get(name: string): string | null } | null): string | null {
  return params?.get('feed') ?? null;
}

/** The layer selected in Settings → Maps; `?layout=` is still read from older links. */
export function mapsSettingsSelectedLayer(params: { get(name: string): string | null } | null): string | null {
  return params?.get('layer') ?? params?.get('layout') ?? null;
}
