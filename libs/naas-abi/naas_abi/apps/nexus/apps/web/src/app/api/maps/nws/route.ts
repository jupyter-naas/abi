import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * NWS active weather alerts (US). Requires User-Agent; proxied to avoid CORS.
 * Upstream: https://api.weather.gov/alerts/active?status=actual
 */
export async function GET() {
  try {
    const res = await mapsUpstreamGet(
      'https://api.weather.gov/alerts/active?status=actual',
      {
        timeoutMs: 25000,
        headers: { Accept: 'application/geo+json' },
      },
    );
    if (!res.ok) {
      return mapsJson(
        { error: `NWS ${res.status}`, pins: [], count: 0 },
        { status: 502 },
      );
    }
    const data = (await res.json()) as {
      features?: Array<{
        id?: string;
        properties?: {
          headline?: string;
          event?: string;
          severity?: string;
          areaDesc?: string;
          senderName?: string;
        };
        geometry?: {
          type?: string;
          coordinates?: unknown;
        } | null;
      }>;
    };

    const pins = [];
    for (const f of data.features ?? []) {
      const centroid = centroidOfGeometry(f.geometry);
      if (!centroid) continue;
      const p = f.properties ?? {};
      const severity = (p.severity ?? '').toLowerCase();
      pins.push({
        id: String(f.id ?? `${centroid.lat},${centroid.lng}`),
        lat: centroid.lat,
        lng: centroid.lng,
        label: p.event ?? p.headline ?? 'Weather alert',
        detail: [p.severity, p.areaDesc, p.senderName]
          .filter(Boolean)
          .join(' · '),
        color:
          severity === 'extreme' || severity === 'severe'
            ? '#dc2626'
            : severity === 'moderate'
              ? '#ea580c'
              : '#2563eb',
      });
    }

    return mapsJson({ pins, source: 'nws', count: pins.length }, { cacheSeconds: 120 });
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

function centroidOfGeometry(
  geometry: { type?: string; coordinates?: unknown } | null | undefined,
): { lat: number; lng: number } | null {
  if (!geometry?.coordinates) return null;
  const pts = flattenCoords(geometry.coordinates);
  if (pts.length === 0) return null;
  let sumLat = 0;
  let sumLng = 0;
  for (const [lng, lat] of pts) {
    sumLat += lat;
    sumLng += lng;
  }
  return { lat: sumLat / pts.length, lng: sumLng / pts.length };
}

function flattenCoords(coords: unknown): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  function walk(node: unknown): void {
    if (!Array.isArray(node) || node.length === 0) return;
    if (typeof node[0] === 'number' && typeof node[1] === 'number') {
      out.push([node[0] as number, node[1] as number]);
      return;
    }
    for (const child of node) walk(child);
  }
  walk(coords);
  return out;
}
