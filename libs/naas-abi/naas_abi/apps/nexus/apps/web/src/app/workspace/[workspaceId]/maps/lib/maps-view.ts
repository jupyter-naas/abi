/** Viewport sent with live Maps feeds (flights, AIS). */

export const MAPS_MAX_VIEWPORT_RADIUS_NM = 250;
export const MAPS_MIN_VIEWPORT_ZOOM = 4;
export const MAPS_MIN_VIEWPORT_RADIUS_NM = 25;

export interface MapsFeedView {
  west: number;
  south: number;
  east: number;
  north: number;
  lat: number;
  lng: number;
  zoom: number;
  radiusNm: number;
}

export interface MapsFeedMeta {
  source?: string;
  attribution?: string;
  observedAt?: string;
  stale?: boolean;
  needsKey?: boolean;
  status?: string;
  coverage?: string;
}

const NM_PER_DEG_LAT = 60;

function wrapLng(lng: number): number {
  if (!Number.isFinite(lng)) return 0;
  const wrapped = ((((lng + 180) % 360) + 360) % 360) - 180;
  return wrapped === -180 ? 180 : wrapped;
}

function clampLat(lat: number): number {
  return Math.min(90, Math.max(-90, lat));
}

/** Approximate nautical miles from a point to another (equirectangular). */
export function mapsNmBetween(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
): number {
  const dLat = (lat2 - lat1) * NM_PER_DEG_LAT;
  const meanLat = ((lat1 + lat2) / 2) * (Math.PI / 180);
  const dLng = (lng2 - lng1) * NM_PER_DEG_LAT * Math.cos(meanLat);
  return Math.hypot(dLat, dLng);
}

export function mapsViewFromBounds(input: {
  west: number;
  south: number;
  east: number;
  north: number;
  lat: number;
  lng: number;
  zoom: number;
}): MapsFeedView {
  const lat = clampLat(input.lat);
  const lng = wrapLng(input.lng);
  const north = clampLat(input.north);
  const south = clampLat(input.south);
  const radiusNm = Math.min(
    MAPS_MAX_VIEWPORT_RADIUS_NM,
    Math.max(
      MAPS_MIN_VIEWPORT_RADIUS_NM,
      mapsNmBetween(lat, lng, north, wrapLng(input.east)),
    ),
  );
  return {
    west: wrapLng(input.west),
    south,
    east: wrapLng(input.east),
    north,
    lat,
    lng,
    zoom: Number.isFinite(input.zoom) ? input.zoom : 2,
    radiusNm,
  };
}

/** True when the view is tight enough for a single point query. */
export function isMapsViewportQuery(view?: MapsFeedView | null): boolean {
  return Boolean(view && view.zoom >= MAPS_MIN_VIEWPORT_ZOOM);
}

export function withMapsView(url: string, view?: MapsFeedView): string {
  if (!view) return url;
  const params = new URLSearchParams({
    lat: view.lat.toFixed(4),
    lng: view.lng.toFixed(4),
    zoom: String(Math.round(view.zoom)),
    radiusNm: String(Math.round(view.radiusNm)),
    west: view.west.toFixed(4),
    south: view.south.toFixed(4),
    east: view.east.toFixed(4),
    north: view.north.toFixed(4),
  });
  return `${url}${url.includes('?') ? '&' : '?'}${params.toString()}`;
}

export function formatMapsFeedAge(iso: string, now = Date.now()): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return '';
  const sec = Math.max(0, Math.round((now - t) / 1000));
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  return `${Math.round(min / 60)}h ago`;
}
