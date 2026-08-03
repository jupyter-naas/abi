import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** Coarse global sample tiles via airplanes.live (no API key). */
const REGIONS = [
  { lat: 40.7, lon: -74.0, radius: 150 },
  { lat: 51.5, lon: -0.1, radius: 150 },
  { lat: 48.9, lon: 2.3, radius: 120 },
  { lat: 25.2, lon: 55.3, radius: 200 },
  { lat: 1.35, lon: 103.8, radius: 150 },
  { lat: 35.7, lon: 139.7, radius: 150 },
  { lat: 37.8, lon: -122.4, radius: 150 },
  { lat: -23.5, lon: -46.6, radius: 150 },
];

type Ac = {
  hex?: string;
  flight?: string;
  lat?: number;
  lon?: number;
  alt_baro?: number | string;
  gs?: number;
  track?: number;
  military?: boolean;
};

/** Maps-owned flights proxy: airplanes.live point queries, deduped by ICAO. */
export async function GET() {
  try {
    const batches = await Promise.all(
      REGIONS.map(async (r) => {
        try {
          const res = await mapsUpstreamGet(
            `https://api.airplanes.live/v2/point/${r.lat}/${r.lon}/${r.radius}`,
            { timeoutMs: 10000 },
          );
          if (!res.ok) return [] as Ac[];
          const data = (await res.json()) as { ac?: Ac[] };
          return data.ac ?? [];
        } catch {
          return [] as Ac[];
        }
      }),
    );

    const seen = new Set<string>();
    const pins: Array<Record<string, unknown>> = [];
    for (const ac of batches.flat()) {
      const id = (ac.hex || '').toLowerCase();
      if (!id || seen.has(id)) continue;
      if (ac.lat == null || ac.lon == null) continue;
      if (!Number.isFinite(ac.lat) || !Number.isFinite(ac.lon)) continue;
      seen.add(id);
      const callsign = (ac.flight || id).trim() || id;
      const alt =
        typeof ac.alt_baro === 'number'
          ? `${Math.round(ac.alt_baro)} ft`
          : String(ac.alt_baro ?? '');
      pins.push({
        id,
        lat: ac.lat,
        lng: ac.lon,
        label: callsign,
        detail: `${alt}${ac.military ? ' · military' : ''} · airplanes.live`,
        color: ac.military ? '#dc2626' : '#2563eb',
        size: 7,
      });
      if (pins.length >= 400) break;
    }

    return mapsJson({
      pins,
      count: pins.length,
      source: 'airplanes.live',
    });
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'Flights fetch failed',
        pins: [],
        count: 0,
      },
      { status: 502 },
    );
  }
}
