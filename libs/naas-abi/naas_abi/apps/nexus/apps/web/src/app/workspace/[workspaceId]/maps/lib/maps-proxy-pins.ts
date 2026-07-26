import type { MapsPinMarker } from './leaflet-map';

interface ProxyPinPayload {
  pins?: Array<{
    id?: string;
    lat?: number;
    lng?: number;
    label?: string;
    detail?: string;
    color?: string;
    size?: number;
  }>;
  error?: string;
  needsKey?: boolean;
  message?: string;
  docs?: string;
  note?: string;
}

export class MapsProxyNeedsKeyError extends Error {
  docs?: string;
  constructor(message: string, docs?: string) {
    super(message);
    this.name = 'MapsProxyNeedsKeyError';
    this.docs = docs;
  }
}

/** Fetch normalized pins from a nexus-web /api/maps/* route. */
export async function fetchMapsProxyPins(
  path: string,
  signal?: AbortSignal,
): Promise<MapsPinMarker[]> {
  const res = await fetch(path, { signal });
  const data = (await res.json()) as ProxyPinPayload;
  if (data.needsKey) {
    throw new MapsProxyNeedsKeyError(
      data.message ?? 'This layer needs an API key.',
      data.docs,
    );
  }
  if (!res.ok) {
    throw new Error(data.error ?? `Proxy ${res.status}`);
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
  return pins;
}
