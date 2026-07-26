import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type NwsFeature = {
  id?: string;
  properties?: {
    id?: string;
    event?: string;
    headline?: string;
    severity?: string;
    areaDesc?: string;
    sent?: string;
  };
  geometry?: {
    type?: string;
    coordinates?: unknown;
  } | null;
};

function centroid(
  geometry: NwsFeature['geometry'],
): { lat: number; lng: number } | null {
  if (!geometry?.coordinates) return null;
  if (geometry.type === 'Point') {
    const coords = geometry.coordinates as number[];
    if (coords.length < 2) return null;
    const [lng, lat] = coords;
    return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null;
  }
  let ring: number[][] | null = null;
  if (geometry.type === 'Polygon') {
    ring = (geometry.coordinates as number[][][])[0] ?? null;
  } else if (geometry.type === 'MultiPolygon') {
    ring = (geometry.coordinates as number[][][][])[0]?.[0] ?? null;
  }
  if (!ring?.length) return null;
  let lngSum = 0;
  let latSum = 0;
  let n = 0;
  for (const pt of ring) {
    if (!pt || pt.length < 2) continue;
    const [lng, lat] = pt;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    lngSum += lng;
    latSum += lat;
    n += 1;
  }
  if (!n) return null;
  return { lat: latSum / n, lng: lngSum / n };
}

/** NWS active alerts GeoJSON. Proxied so User-Agent is always set. */
export async function GET() {
  try {
    const res = await mapsUpstreamGet(
      'https://api.weather.gov/alerts/active?status=actual',
      { timeoutMs: 25000 },
    );
    if (!res.ok) {
      return mapsJson(
        { error: `NWS ${res.status}`, pins: [], count: 0 },
        { status: 502 },
      );
    }
    const data = (await res.json()) as { features?: NwsFeature[] };
    const pins: Array<Record<string, unknown>> = [];
    for (const f of data.features ?? []) {
      const c = centroid(f.geometry);
      if (!c) continue;
      const p = f.properties ?? {};
      const severity = p.severity ?? 'Unknown';
      const event = p.event ?? 'Alert';
      pins.push({
        id: String(p.id ?? f.id ?? `${c.lat},${c.lng}`),
        lat: c.lat,
        lng: c.lng,
        label: event,
        detail: `${severity} · ${p.areaDesc ?? 'NWS'}`,
        color:
          severity === 'Extreme'
            ? '#7f1d1d'
            : severity === 'Severe'
              ? '#dc2626'
              : severity === 'Moderate'
                ? '#ea580c'
                : '#ca8a04',
        size: severity === 'Extreme' || severity === 'Severe' ? 11 : 8,
      });
      if (pins.length >= 250) break;
    }
    return mapsJson({ pins, count: pins.length, source: 'api.weather.gov' });
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'NWS fetch failed',
        pins: [],
        count: 0,
      },
      { status: 502 },
    );
  }
}
