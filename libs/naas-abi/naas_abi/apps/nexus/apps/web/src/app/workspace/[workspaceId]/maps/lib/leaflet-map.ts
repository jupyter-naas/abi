import type { Map as LeafletMap, Marker } from 'leaflet';
import {
  isMapsDarkMode,
  MAPS_TILE_ATTR,
  MAPS_TILE_DARK,
  MAPS_TILE_LIGHT,
} from './leaflet-tiles';

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
  size?: number;
}

/** Escape text for Leaflet popup HTML. */
export function escapeMapsHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function mapsPinHtml(color: string, size: number): string {
  return `<span style="display:block;width:${size}px;height:${size}px;border:2px solid #fff;background:${color};box-shadow:0 1px 4px rgba(0,0,0,.35);border-radius:var(--org-border-radius,0px)"></span>`;
}

export async function createMapsLeaflet(
  container: HTMLElement,
  view: { center?: MapsLatLng; zoom?: number } = {},
): Promise<{ L: typeof import('leaflet'); map: LeafletMap }> {
  const L = await import('leaflet');
  await import('leaflet/dist/leaflet.css');
  const map = L.map(container, {
    zoomControl: true,
    attributionControl: true,
  });
  L.tileLayer(isMapsDarkMode() ? MAPS_TILE_DARK : MAPS_TILE_LIGHT, {
    attribution: MAPS_TILE_ATTR,
    maxZoom: 18,
  }).addTo(map);
  map.setView(
    [view.center?.lat ?? 20, view.center?.lng ?? 0],
    view.zoom ?? 2,
  );
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
): MapsLatLng[] {
  const bounds: MapsLatLng[] = [];
  for (const pin of pins) {
    const size = pin.size ?? 10;
    const color = pin.color ?? '#2563eb';
    const icon = L.divIcon({
      className: 'maps-pin-icon',
      html: mapsPinHtml(color, size),
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
    const marker = L.marker([pin.lat, pin.lng], { icon }).addTo(map);
    const detailHtml = pin.detail
      ? `<div class="maps-pin-popup__meta">${escapeMapsHtml(pin.detail)}</div>`
      : '';
    marker.bindPopup(
      `<div class="maps-pin-popup"><strong>${escapeMapsHtml(pin.label)}</strong>${detailHtml}</div>`,
    );
    markers.push(marker);
    bounds.push({ lat: pin.lat, lng: pin.lng });
  }
  return bounds;
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
