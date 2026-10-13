/**
 * Deployment switches for Maps (build-time env). Which layers a workspace shows
 * is not one of them: deployments hide layers per workspace through seeds
 * (`register_maps_seeds(hidden_layouts=...)`) and admins in Settings → Maps.
 */

/** Comma-separated feed ids from NEXT_PUBLIC_MAPS_DEFAULT_ON_FEED_IDS. */
export function parseMapsDefaultOnFeedIds(
  raw: string | null | undefined,
): ReadonlySet<string> | null {
  const text = (raw ?? '').trim();
  if (!text) return null;
  const ids = text
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
  return ids.length ? new Set(ids) : null;
}

export const MAPS_DEFAULT_ON_FEED_IDS = parseMapsDefaultOnFeedIds(
  process.env.NEXT_PUBLIC_MAPS_DEFAULT_ON_FEED_IDS,
);

/** Static default feeds from env (before URL / workspace API overrides). */
export function mapsDefaultOnFeedIds(): ReadonlySet<string> {
  return MAPS_DEFAULT_ON_FEED_IDS ?? new Set();
}

/** Hide File → New layer / New basemap / GeoJSON layers and Settings → New layer. */
export function mapsDeploymentRestrictsLayerCatalog(): boolean {
  return process.env.NEXT_PUBLIC_MAPS_RESTRICT_LAYER_CATALOG === 'true';
}
