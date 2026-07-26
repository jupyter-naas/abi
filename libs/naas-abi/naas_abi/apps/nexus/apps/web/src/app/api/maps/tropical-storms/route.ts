import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const CLASS_COLORS: Record<string, string> = {
  HU: '#7f1d1d',
  MH: '#450a0a',
  TS: '#ea580c',
  TD: '#ca8a04',
  STS: '#ea580c',
  PTC: '#64748b',
};

/** NHC active tropical cyclones (CurrentStorms.json). */
export async function GET() {
  try {
    const res = await mapsUpstreamGet(
      'https://www.nhc.noaa.gov/CurrentStorms.json',
      { timeoutMs: 20000 },
    );
    if (!res.ok) {
      return mapsJson(
        { error: `NHC ${res.status}`, pins: [], count: 0 },
        { status: 502 },
      );
    }
    const data = (await res.json()) as {
      activeStorms?: Array<{
        id?: string;
        name?: string;
        classification?: string;
        intensity?: string;
        latitudeNumeric?: number;
        longitudeNumeric?: number;
        lastUpdate?: string;
      }>;
    };
    const pins: Array<Record<string, unknown>> = [];
    for (const storm of data.activeStorms ?? []) {
      const lat = storm.latitudeNumeric;
      const lng = storm.longitudeNumeric;
      if (lat == null || lng == null) continue;
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      const cls = storm.classification ?? 'TC';
      const name = storm.name ?? storm.id ?? 'Storm';
      pins.push({
        id: String(storm.id ?? `${lat},${lng}`),
        lat,
        lng,
        label: `${cls} ${name}`,
        detail: `${storm.intensity ?? '?'} kt · NHC${storm.lastUpdate ? ` · ${storm.lastUpdate}` : ''}`,
        color: CLASS_COLORS[cls] ?? '#2563eb',
        size: 14,
      });
    }
    return mapsJson({
      pins,
      count: pins.length,
      source: 'nhc.noaa.gov',
    });
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'NHC fetch failed',
        pins: [],
        count: 0,
      },
      { status: 502 },
    );
  }
}
