import { mapsJson, mapsProxyError, mapsUpstreamGet } from '../_shared';

/** ISS current position via open-notify (CORS-safe proxy). */
export async function GET() {
  try {
    const res = await mapsUpstreamGet(
      'http://api.open-notify.org/iss-now.json',
      { timeoutMs: 10000, cacheSeconds: 10 },
    );
    if (!res.ok) return mapsProxyError(`ISS ${res.status}`, 502);
    const data = (await res.json()) as {
      iss_position?: { latitude?: string; longitude?: string };
      timestamp?: number;
    };
    const lat = Number(data.iss_position?.latitude);
    const lng = Number(data.iss_position?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return mapsProxyError('ISS position missing', 502);
    }
    return mapsJson(
      {
        pins: [
          {
            id: 'iss',
            lat,
            lng,
            label: 'ISS',
            detail: data.timestamp
              ? new Date(data.timestamp * 1000).toUTCString()
              : 'open-notify',
            color: '#7c3aed',
            size: 14,
          },
        ],
        source: 'open-notify',
      },
      { cacheSeconds: 10 },
    );
  } catch (err) {
    return mapsProxyError(
      err instanceof Error ? err.message : 'ISS fetch failed',
    );
  }
}
