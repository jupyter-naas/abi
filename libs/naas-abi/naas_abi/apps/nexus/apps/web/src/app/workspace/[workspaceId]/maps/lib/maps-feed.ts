import type { MapsPinMarker } from './leaflet-map';

export interface MapsFeedPayload {
  pins?: Array<{
    id?: string;
    lat?: number;
    lng?: number;
    label?: string;
    detail?: string;
    color?: string;
    size?: number;
  }>;
  count?: number;
  empty?: boolean;
  reason?: string;
  message?: string;
  error?: string;
  source?: string;
  needsKey?: boolean;
}

/** Fetch a Maps /api/maps/* JSON pin payload (empty/needsKey stays empty, not thrown). */
export async function fetchMapsFeedPins(
  url: string,
  signal?: AbortSignal,
  headers?: HeadersInit,
): Promise<{ pins: MapsPinMarker[]; reason?: string; empty?: boolean }> {
  const res = await fetch(url, { signal, headers });
  const data = (await res.json()) as MapsFeedPayload;
  if (!res.ok && !(data.pins && data.pins.length) && !data.empty && !data.needsKey) {
    throw new Error(data.error || data.message || `Feed ${res.status}`);
  }
  const pins: MapsPinMarker[] = [];
  for (const p of data.pins ?? []) {
    if (p.lat == null || p.lng == null) continue;
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lng)) continue;
    pins.push({
      id: String(p.id ?? `${p.lat},${p.lng}`),
      lat: p.lat,
      lng: p.lng,
      label: p.label ?? 'Point',
      detail: p.detail,
      color: p.color,
      size: p.size,
    });
  }
  return {
    pins,
    reason: data.reason || data.message,
    empty: data.empty || data.needsKey || pins.length === 0,
  };
}

/** Parse EONET events JSON into map pins (latest Point geometry per event). */
export function eonetEventsToPins(
  data: {
    events?: Array<{
      id?: string;
      title?: string;
      link?: string;
      categories?: Array<{ id?: string; title?: string }>;
      geometry?: Array<{
        type?: string;
        coordinates?: number[];
        date?: string;
      }>;
    }>;
  },
  color = '#7c3aed',
): MapsPinMarker[] {
  const pins: MapsPinMarker[] = [];
  for (const event of data.events ?? []) {
    const geoms = event.geometry ?? [];
    const point = [...geoms].reverse().find((g) => g.type === 'Point');
    const coords = point?.coordinates;
    if (!coords || coords.length < 2) continue;
    const [lng, lat] = coords;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    const cat = event.categories?.[0]?.title ?? 'EONET';
    const catId = event.categories?.[0]?.id;
    pins.push({
      id: String(event.id ?? `${lat},${lng}`),
      lat,
      lng,
      label: event.title ?? 'EONET event',
      detail: `${cat}${point?.date ? ` · ${point.date}` : ''}`,
      color:
        catId === 'wildfires'
          ? '#dc2626'
          : catId === 'volcanoes'
            ? '#7c3aed'
            : catId === 'severeStorms'
              ? '#2563eb'
              : catId === 'earthquakes'
                ? '#ea580c'
                : color,
      size: 9,
    });
  }
  return pins;
}
