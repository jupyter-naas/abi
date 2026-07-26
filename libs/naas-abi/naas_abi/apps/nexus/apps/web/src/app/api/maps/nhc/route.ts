import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * NOAA NHC current tropical storms (CORS-safe proxy).
 * Upstream: https://www.nhc.noaa.gov/CurrentStorms.json
 */
export async function GET() {
  try {
    const res = await mapsUpstreamGet(
      'https://www.nhc.noaa.gov/CurrentStorms.json',
      { timeoutMs: 15000 },
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
        binNumber?: string;
        name?: string;
        classification?: string;
        intensity?: string;
        pressure?: string;
        latitude?: string | number;
        longitude?: string | number;
        latitudeNumeric?: number;
        longitudeNumeric?: number;
      }>;
    };

    const pins = [];
    for (const s of data.activeStorms ?? []) {
      const lat =
        typeof s.latitudeNumeric === 'number'
          ? s.latitudeNumeric
          : parseCoord(s.latitude);
      const lng =
        typeof s.longitudeNumeric === 'number'
          ? s.longitudeNumeric
          : parseCoord(s.longitude);
      if (lat == null || lng == null) continue;
      pins.push({
        id: String(s.id ?? s.binNumber ?? s.name ?? `${lat},${lng}`),
        lat,
        lng,
        label: s.name ?? 'Tropical cyclone',
        detail: [s.classification, s.intensity, s.pressure]
          .filter(Boolean)
          .join(' · '),
        color: '#7c3aed',
        size: 14,
      });
    }

    return mapsJson(
      { pins, source: 'nhc', count: pins.length },
      { cacheSeconds: 300 },
    );
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

function parseCoord(value: string | number | undefined): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  const match = /^(-?\d+(?:\.\d+)?)\s*([NSEW])?$/i.exec(trimmed);
  if (!match) {
    const n = Number(trimmed);
    return Number.isFinite(n) ? n : null;
  }
  let n = Number(match[1]);
  const hemi = (match[2] || '').toUpperCase();
  if (hemi === 'S' || hemi === 'W') n = -Math.abs(n);
  if (hemi === 'N' || hemi === 'E') n = Math.abs(n);
  return Number.isFinite(n) ? n : null;
}
