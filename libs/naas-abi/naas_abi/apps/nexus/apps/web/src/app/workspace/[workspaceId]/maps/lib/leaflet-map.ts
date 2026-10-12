import type { Map as LeafletMap, Marker } from 'leaflet';
import {
  isMapsDarkMode,
  MAPS_TILE_ATTR,
  MAPS_TILE_DARK,
  MAPS_TILE_LIGHT,
} from './leaflet-tiles';
import { MAPS_LAYER_MARKER_PX, mapsLayerLogoPinHtml, mapsLayerPinHtml } from './maps-layer-pin-html';
import { resolveMapsPinImageUrl } from './maps-pin-image-url';
import { resolvePinMedia } from './maps-pin-media';

export interface MapsLatLng {
  lat: number;
  lng: number;
}

export interface MapsPinMarker {
  id: string;
  lat: number;
  lng: number;
  label: string;
  detail?: string;
  color?: string;
  /** Lucide key (mapsIconMap) for badge pins on the combined map. */
  markerIcon?: string;
  /** HTTPS logo URL for map pins (overrides markerIcon when set). */
  markerLogoUrl?: string;
  size?: number;
  entityUri?: string;
  graphUri?: string;
  classLabel?: string;
  /** Every feature type when the feature has several (e.g. Valeo activity poles). */
  classLabels?: string[];
  country?: string;
  precision?: string;
  observedAt?: string;
  sources?: Array<{title: string; url: string}>;
  memberIds?: string[];
  relationships?: Array<{label: string; value: string; entityUri?: string}>;
  address?: string;
  photoUrl?: string;
  photoSource?: string;
  streetViewUrl?: string;
  streetViewFallbackUrl?: string;
  imageSearchUrl?: string;
  websiteUrl?: string;
  phone?: string;
  /** Layer the pin belongs to on the combined map (color / group-by-country). */
  layerId?: string;
  /** The layer's color (group-by-country by layer). */
  layerColor?: string;
  /** Feed of the layer and its color / title (group-by-country by feed). */
  feedId?: string;
  feedColor?: string;
  feedTitle?: string;
  /** The feature's id in its feed (the same site in several layers). */
  featureId?: string;
  /** Country aggregate marker (toolbar “group by country”). */
  clusterCount?: number;
  /** Country aggregate: one numbered badge per layer, in the layer's color. */
  clusterLayers?: Array<{ layerId: string; title?: string; color: string; count: number }>;
}

/** Escape text for Leaflet popup HTML. */
export function escapeMapsHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function mapsPinPopupHtml(pin: MapsPinMarker): string {
  const media = resolvePinMedia(pin);
  const addressHtml = pin.address
    ? `<div class="maps-pin-popup__meta">${escapeMapsHtml(pin.address)}</div>`
    : '';
  const detailHtml = pin.detail
    ? `<div class="maps-pin-popup__meta">${escapeMapsHtml(pin.detail)}</div>`
    : '';
  const previewSrc = media.photoUrl ?? media.previewUrl;
  const previewHtml = `<a class="maps-pin-popup__photo" href="${escapeMapsHtml(media.streetViewUrl)}" target="_blank" rel="noreferrer"><img src="${escapeMapsHtml(previewSrc)}" alt="" referrerpolicy="no-referrer"/></a>`;
  return `<div class="maps-pin-popup"><strong>${escapeMapsHtml(pin.label)}</strong>${addressHtml}${detailHtml}${previewHtml}<div class="maps-pin-popup__actions"><a class="maps-pin-popup__streetview-btn" href="${escapeMapsHtml(media.streetViewUrl)}" target="_blank" rel="noreferrer">Open Street View</a></div></div>`;
}

export const MAPS_USER_LOCATION_COLOR = '#4285F4';

export function mapsPinHtml(color: string, size: number): string {
  return `<span style="display:block;width:${size}px;height:${size}px;border:2px solid #fff;background:${color};box-shadow:0 1px 4px rgba(0,0,0,.35);border-radius:0"></span>`;
}

/** Every count is shown (no "99+"): up to 999 as is, then 1.2k, 15k. */
export function clusterCountLabel(count: number): string {
  if (count < 1000) return String(count);
  const thousands = count / 1000;
  return `${thousands < 10 ? Math.floor(thousands * 10) / 10 : Math.floor(thousands)}k`;
}

const SAFE_COLOR = /^#[0-9a-f]{3,8}$/i;

export function mapsCountryClusterPinHtml(color: string, count: number, size = 28): string {
  const fill = SAFE_COLOR.test(color) ? color : '#2563eb';
  const label = clusterCountLabel(count);
  // Three characters still fit the badge with a smaller font.
  const font = label.length >= 3 ? 'font-size:9px;letter-spacing:-0.02em;' : '';
  return `<span class="maps-country-cluster-pin" style="--maps-cluster-color:${fill};width:${size}px;height:${size}px;${font}"><span class="maps-country-cluster-pin__count">${label}</span></span>`;
}

/** Country markers: badges per row, and badge size once a country has several. */
export const MAPS_CLUSTER_BADGE_COLUMNS = 3;
export const MAPS_CLUSTER_GRID_BADGE_PX = 24;
const MAPS_CLUSTER_GAP_PX = 2;

/** Pixel box of a country marker with `badges` badges, laid out in a centered grid. */
export function mapsCountryClusterBox(badges: number, size = 28): { width: number; height: number } {
  if (badges <= 1) return { width: size, height: size };
  const cell = MAPS_CLUSTER_GRID_BADGE_PX;
  const columns = Math.min(MAPS_CLUSTER_BADGE_COLUMNS, badges);
  const rows = Math.ceil(badges / columns);
  return {
    width: columns * cell + (columns - 1) * MAPS_CLUSTER_GAP_PX,
    height: rows * cell + (rows - 1) * MAPS_CLUSTER_GAP_PX,
  };
}

/**
 * Country marker: one numbered badge per layer (or feed), each in its color, in
 * a compact grid centered on the country so several layers never stack.
 */
export function mapsCountryClusterLayersHtml(
  layers: NonNullable<MapsPinMarker['clusterLayers']>,
  size = 28,
): string {
  const badgeSize = layers.length > 1 ? MAPS_CLUSTER_GRID_BADGE_PX : size;
  const columns = Math.min(MAPS_CLUSTER_BADGE_COLUMNS, Math.max(1, layers.length));
  const badges = layers
    .map((layer) => {
      const title = layer.title ? ` title="${escapeMapsHtml(`${layer.count} ${layer.title}`)}"` : '';
      return `<span${title}>${mapsCountryClusterPinHtml(layer.color, layer.count, badgeSize)}</span>`;
    })
    .join('');
  return `<span class="maps-country-cluster-group" style="grid-template-columns:repeat(${columns},${badgeSize}px);gap:${MAPS_CLUSTER_GAP_PX}px">${badges}</span>`;
}

/** Google Maps–style blue dot for the device location. */
export function mapsUserLocationPinHtml(size = 16): string {
  return `<span style="display:block;width:${size}px;height:${size}px;border:2px solid #fff;background:${MAPS_USER_LOCATION_COLOR};box-shadow:0 1px 4px rgba(0,0,0,.35);border-radius:50%"></span>`;
}

/** Default zoom when centering on the device location (Google Maps–like street scale). */
export const MAPS_LOCATE_ZOOM = 17;

export function mapsLocateZoomForAccuracy(accuracyMeters: number | null | undefined): number {
  if (accuracyMeters == null || !Number.isFinite(accuracyMeters)) return MAPS_LOCATE_ZOOM;
  if (accuracyMeters <= 50) return 17;
  if (accuracyMeters <= 500) return 15;
  return 13;
}

export function flyMapToUserLocation(
  map: LeafletMap,
  lat: number,
  lng: number,
  accuracyMeters?: number,
): void {
  const zoom = mapsLocateZoomForAccuracy(accuracyMeters);
  map.flyTo([lat, lng], zoom, { duration: 0.65 });
}

export function createUserLocationMarker(
  L: typeof import('leaflet'),
  map: LeafletMap,
  lat: number,
  lng: number,
): Marker {
  const size = 16;
  const icon = L.divIcon({
    className: 'maps-pin-icon maps-user-location-pin',
    html: mapsUserLocationPinHtml(size),
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
  return L.marker([lat, lng], { icon, title: 'Your location', zIndexOffset: 1000 }).addTo(map);
}

/** Zoom +/- control: bottom-right, squared (see maps-components.css). */
export function attachMapsZoomControl(L: typeof import('leaflet'), map: LeafletMap): void {
  L.control.zoom({ position: 'bottomright' }).addTo(map);
}

type LeafletMapInternal = LeafletMap & {
  _mapPane?: HTMLElement | null;
};

/**
 * True when the map still has a live container and initialized map pane.
 * Prevents `_leaflet_pos` crashes after route change / Strict Mode remount.
 */
export function canInvalidateMapsLeaflet(map: LeafletMap | null | undefined): boolean {
  if (!map || typeof map.invalidateSize !== 'function') return false;
  try {
    const container = map.getContainer?.();
    if (!container) return false;
    // Detached DOM: skip. Plain mocks omit isConnected (undefined → allow).
    if (container.isConnected === false) return false;

    const internal = map as LeafletMapInternal;
    const mapPane =
      (typeof map.getPane === 'function' ? map.getPane('mapPane') : undefined) ??
      internal._mapPane;

    if (mapPane && mapPane.isConnected === false) return false;
    // Real Leaflet instances expose _mapPane; null/undefined means torn down.
    if (Object.prototype.hasOwnProperty.call(internal, '_mapPane') && !internal._mapPane) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

/** Safe invalidateSize: no-op when torn down; swallow Leaflet teardown races. */
export function safeInvalidateMapsLeafletSize(map: LeafletMap): void {
  if (!canInvalidateMapsLeaflet(map)) return;
  try {
    map.invalidateSize({ animate: false });
  } catch {
    // Container/pane removed between guard and Leaflet internals.
  }
}

/**
 * Keep Leaflet in sync when the map container resizes (sidebar / section panel /
 * AI pane / window). Panel collapse uses a ~300ms CSS transition, so we invalidate
 * on the next frame and again after the transition settles.
 */
export function observeMapsLeafletSize(map: LeafletMap): () => void {
  const container = map.getContainer();
  let rafId = 0;
  let timeoutId = 0;
  let stopped = false;

  const invalidate = () => {
    if (stopped) return;
    if (rafId) cancelAnimationFrame(rafId);
    if (timeoutId) window.clearTimeout(timeoutId);
    rafId = requestAnimationFrame(() => {
      rafId = 0;
      if (stopped) return;
      safeInvalidateMapsLeafletSize(map);
      timeoutId = window.setTimeout(() => {
        timeoutId = 0;
        if (stopped) return;
        safeInvalidateMapsLeafletSize(map);
      }, 320);
    });
  };

  const ro = new ResizeObserver(invalidate);
  ro.observe(container);
  window.addEventListener('resize', invalidate);
  invalidate();

  const stop = () => {
    if (stopped) return;
    stopped = true;
    if (rafId) cancelAnimationFrame(rafId);
    if (timeoutId) window.clearTimeout(timeoutId);
    rafId = 0;
    timeoutId = 0;
    ro.disconnect();
    window.removeEventListener('resize', invalidate);
  };
  map.once('unload', stop);
  return stop;
}

function addOsmTiles(L: typeof import('leaflet'), map: LeafletMap): void {
  L.tileLayer(isMapsDarkMode() ? MAPS_TILE_DARK : MAPS_TILE_LIGHT, {
    className: 'maps-basemap',
    attribution: MAPS_TILE_ATTR,
    maxZoom: 18,
  }).addTo(map);
}

export async function createMapsLeaflet(
  container: HTMLElement,
  view: { center?: MapsLatLng; zoom?: number } = {},
  signal?: AbortSignal,
): Promise<{ L: typeof import('leaflet'); map: LeafletMap }> {
  signal?.throwIfAborted();
  const L = await import('leaflet');
  await import('leaflet/dist/leaflet.css');
  // Strict Mode cleanup or navigation can happen while the modules load.
  // Check before Leaflet claims the DOM container, not after creating the map.
  signal?.throwIfAborted();
  const map = L.map(container, {
    zoomControl: false,
    attributionControl: true,
  });
  attachMapsZoomControl(L, map);
  map.setView(
    [view.center?.lat ?? MAPS_DEFAULT_CAMERA.lat, view.center?.lng ?? MAPS_DEFAULT_CAMERA.lng],
    view.zoom ?? MAPS_DEFAULT_CAMERA.zoom,
  );
  observeMapsLeafletSize(map);
  return { L, map };
}

export function clearMapsMarkers(markers: Marker[]): void {
  markers.forEach((m) => m.remove());
  markers.length = 0;
}

export function addMapsPinMarkers(
  L: typeof import('leaflet'),
  map: LeafletMap,
  pins: MapsPinMarker[],
  markers: Marker[],
  onSelect?: (pin: MapsPinMarker) => void,
): MapsLatLng[] {
  const bounds: MapsLatLng[] = [];
  for (const pin of pins) {
    const logoUrl = resolveMapsPinImageUrl(pin.markerLogoUrl);
    const layerBadge = pin.color && (logoUrl || pin.markerIcon);
    // Country markers, including single-site countries (group by country).
    const cluster = pin.clusterCount != null && pin.clusterCount >= 1 && Boolean(pin.memberIds?.length);
    const size = cluster ? 28 : layerBadge ? MAPS_LAYER_MARKER_PX : (pin.size ?? 10);
    const color = pin.color ?? '#2563eb';
    const clusterLayers = cluster ? pin.clusterLayers ?? [] : [];
    const box = cluster ? mapsCountryClusterBox(clusterLayers.length, size) : { width: size, height: size };
    const badgeHtml = cluster
      ? clusterLayers.length > 0
        ? mapsCountryClusterLayersHtml(clusterLayers, size)
        : mapsCountryClusterPinHtml(color, pin.clusterCount ?? 0, size)
      : logoUrl
        ? mapsLayerLogoPinHtml(logoUrl, color)
        : pin.markerIcon
          ? mapsLayerPinHtml(pin.markerIcon, color)
          : mapsPinHtml(color, size);
    const icon = L.divIcon({
      className: cluster ? 'maps-pin-icon maps-pin-icon--cluster' : 'maps-pin-icon',
      html: cluster || layerBadge ? badgeHtml : mapsPinHtml(color, size),
      iconSize: [box.width, box.height],
      iconAnchor: [box.width / 2, box.height / 2],
    });
    const marker = L.marker([pin.lat, pin.lng], { icon, title: pin.label }).addTo(map);
    // With onSelect the canvas shows the pin under its search box (no popup).
    if (onSelect) {
      marker.on('click', () => onSelect(pin));
    } else {
      marker.bindPopup(mapsPinPopupHtml(pin));
    }
    markers.push(marker);
    bounds.push({ lat: pin.lat, lng: pin.lng });
  }
  return bounds;
}

export type MapsCamera = {
  lat: number;
  lng: number;
  zoom: number;
};

/** Initial view before fit-bounds or user interaction (matches createMapsLeaflet). */
export const MAPS_DEFAULT_CAMERA: MapsCamera = { lat: 20, lng: 0, zoom: 2 };

export function captureMapsCamera(map: LeafletMap): MapsCamera {
  const center = map.getCenter();
  return { lat: center.lat, lng: center.lng, zoom: map.getZoom() };
}

export function restoreMapsCamera(map: LeafletMap, camera: MapsCamera): void {
  if (typeof map.flyTo === 'function') {
    map.flyTo([camera.lat, camera.lng], camera.zoom, { duration: 0.55 });
    return;
  }
  map.setView([camera.lat, camera.lng], camera.zoom);
}

export function fitMapsBounds(
  map: LeafletMap,
  bounds: MapsLatLng[],
  opts?: { maxZoom?: number; padding?: number },
): void {
  if (bounds.length > 1) {
    map.fitBounds(
      bounds.map((b) => [b.lat, b.lng] as [number, number]),
      {
        padding: [opts?.padding ?? 40, opts?.padding ?? 40],
        maxZoom: opts?.maxZoom ?? 5,
      },
    );
  } else if (bounds.length === 1) {
    map.setView([bounds[0].lat, bounds[0].lng], opts?.maxZoom ?? 4);
  }
}

export function destroyMapsLeaflet(
  map: LeafletMap | null,
  markers: Marker[],
): void {
  clearMapsMarkers(markers);
  map?.remove();
}
