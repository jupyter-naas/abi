/**
 * Deployment switches for Maps (build-time env). Which feeds a workspace starts
 * with is not one of them: it is the workspace's `maps` block in
 * `config.*.yaml`, then admins in Settings → Maps.
 */

/** Hide File → New layer / New basemap / GeoJSON layers and Settings → New layer. */
export function mapsDeploymentRestrictsLayerCatalog(): boolean {
  return process.env.NEXT_PUBLIC_MAPS_RESTRICT_LAYER_CATALOG === 'true';
}
