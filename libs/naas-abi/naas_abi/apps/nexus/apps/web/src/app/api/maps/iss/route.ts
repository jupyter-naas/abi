import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** ISS current position via open-notify (CORS-safe proxy). */
export async function GET() {
  try {
    const res = await mapsUpstreamGet(
      'http://api.open-notify.org/iss-now.json',
      { timeoutMs: 10000 },
    );
    if (!res.ok) {
      return mapsJson(
        { error: `ISS ${res.status}`, pins: [], count: 0 },
        { status: 502 },
      );
    }
    const data = (await res.json()) as {
      iss_position?: { latitude?: string; longitude?: string };
      timestamp?: number;
    };
    const lat = Number(data.iss_position?.latitude);
    const lng = Number(data.iss_position?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return mapsJson(
        { error: 'ISS position missing', pins: [], count: 0 },
        { status: 502 },
      );
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
        count: 1,
      },
      { cacheSeconds: 10 },
    );
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'ISS fetch failed',
        pins: [],
        count: 0,
      },
      { status: 502 },
    );
  }
}
