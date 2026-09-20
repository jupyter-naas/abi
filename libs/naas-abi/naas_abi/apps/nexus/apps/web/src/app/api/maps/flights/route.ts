import { mapsJson, mapsUpstreamGet } from '../_lib';
import {
  MAPS_MAX_VIEWPORT_RADIUS_NM,
  MAPS_MIN_VIEWPORT_ZOOM,
} from '@/app/workspace/[workspaceId]/maps/lib/maps-view';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const FLIGHT_PIN_LIMIT = 400;

/** Coarse global sample when the map is zoomed out past a useful viewport. */
const SAMPLE_REGIONS = [
  { lat: 40.7, lon: -74.0, radius: 150 },
  { lat: 51.5, lon: -0.1, radius: 150 },
  { lat: 48.9, lon: 2.3, radius: 120 },
  { lat: 25.2, lon: 55.3, radius: 200 },
  { lat: 1.35, lon: 103.8, radius: 150 },
  { lat: 35.7, lon: 139.7, radius: 150 },
  { lat: 37.8, lon: -122.4, radius: 150 },
  { lat: -23.5, lon: -46.6, radius: 150 },
];

export type FlightAc = {
  hex?: string;
  flight?: string;
  lat?: number;
  lon?: number;
  alt_baro?: number | string;
  gs?: number;
  track?: number;
  military?: boolean;
};

export type FlightsQuery =
  | { mode: 'viewport'; lat: number; lng: number; radiusNm: number }
  | { mode: 'sample' };

export function parseFlightsQuery(searchParams: URLSearchParams): FlightsQuery {
  const lat = Number(searchParams.get('lat'));
  const lng = Number(searchParams.get('lng'));
  const zoom = Number(searchParams.get('zoom'));
  const radiusNm = Number(searchParams.get('radiusNm'));
  const usableRadius =
    Number.isFinite(radiusNm) && radiusNm > 0
      ? Math.min(MAPS_MAX_VIEWPORT_RADIUS_NM, Math.round(radiusNm))
      : MAPS_MAX_VIEWPORT_RADIUS_NM;
  if (
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    Math.abs(lat) <= 90 &&
    Math.abs(lng) <= 180 &&
    Number.isFinite(zoom) &&
    zoom >= MAPS_MIN_VIEWPORT_ZOOM
  ) {
    return { mode: 'viewport', lat, lng, radiusNm: Math.max(25, usableRadius) };
  }
  return { mode: 'sample' };
}

export function aircraftToPin(
  ac: FlightAc,
  source: string,
): Record<string, unknown> | null {
  const id = (ac.hex || '').toLowerCase();
  if (!id || ac.lat == null || ac.lon == null) return null;
  if (!Number.isFinite(ac.lat) || !Number.isFinite(ac.lon)) return null;
  if (Math.abs(ac.lat) > 90 || Math.abs(ac.lon) > 180) return null;
  const callsign = (ac.flight || id).trim() || id;
  const alt =
    typeof ac.alt_baro === 'number'
      ? `${Math.round(ac.alt_baro)} ft`
      : String(ac.alt_baro ?? '');
  const gs = typeof ac.gs === 'number' ? `${Math.round(ac.gs)} kt` : '';
  return {
    id,
    lat: ac.lat,
    lng: ac.lon,
    label: callsign,
    detail: [alt, gs, ac.military ? 'military' : '', source]
      .filter(Boolean)
      .join(' · '),
    color: ac.military ? '#dc2626' : '#2563eb',
    size: 7,
    sources: [
      {
        title: source,
        url:
          source === 'adsb.lol'
            ? 'https://adsb.lol/'
            : 'https://airplanes.live/',
      },
    ],
  };
}

export function collectFlightPins(
  aircraft: FlightAc[],
  source: string,
  limit = FLIGHT_PIN_LIMIT,
): Array<Record<string, unknown>> {
  const seen = new Set<string>();
  const pins: Array<Record<string, unknown>> = [];
  for (const ac of aircraft) {
    const pin = aircraftToPin(ac, source);
    if (!pin) continue;
    const id = String(pin.id);
    if (seen.has(id)) continue;
    seen.add(id);
    pins.push(pin);
    if (pins.length >= limit) break;
  }
  return pins;
}

async function fetchPoint(
  lat: number,
  lon: number,
  radiusNm: number,
  source: 'adsb.lol' | 'airplanes.live',
): Promise<FlightAc[]> {
  const url =
    source === 'adsb.lol'
      ? `https://api.adsb.lol/v2/lat/${lat}/lon/${lon}/dist/${radiusNm}`
      : `https://api.airplanes.live/v2/point/${lat}/${lon}/${radiusNm}`;
  const res = await mapsUpstreamGet(url, { timeoutMs: 10000 });
  if (!res.ok) return [];
  const data = (await res.json()) as { ac?: FlightAc[] };
  return data.ac ?? [];
}

async function viewportAircraft(
  lat: number,
  lng: number,
  radiusNm: number,
): Promise<{ aircraft: FlightAc[]; source: string; stale?: boolean }> {
  const roundedLat = Math.round(lat * 4) / 4;
  const roundedLng = Math.round(lng * 4) / 4;
  try {
    const adsb = await fetchPoint(roundedLat, roundedLng, radiusNm, 'adsb.lol');
    if (adsb.length) return { aircraft: adsb, source: 'adsb.lol' };
  } catch {
    // Fall through to airplanes.live.
  }
  const live = await fetchPoint(
    roundedLat,
    roundedLng,
    radiusNm,
    'airplanes.live',
  );
  return { aircraft: live, source: 'airplanes.live' };
}

async function sampleAircraft(): Promise<{ aircraft: FlightAc[]; source: string }> {
  const batches = await Promise.all(
    SAMPLE_REGIONS.map(async (region) => {
      try {
        return await fetchPoint(region.lat, region.lon, region.radius, 'airplanes.live');
      } catch {
        return [] as FlightAc[];
      }
    }),
  );
  return { aircraft: batches.flat(), source: 'airplanes.live' };
}

/** Maps-owned flights proxy: viewport adsb.lol, global airplanes.live sample. */
export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const query = parseFlightsQuery(url.searchParams);
    const fetched =
      query.mode === 'viewport'
        ? await viewportAircraft(query.lat, query.lng, query.radiusNm)
        : await sampleAircraft();
    const pins = collectFlightPins(fetched.aircraft, fetched.source);
    const observedAt = new Date().toISOString();
    const attribution =
      fetched.source === 'adsb.lol'
        ? 'adsb.lol (ODbL)'
        : 'airplanes.live';
    const coverage =
      query.mode === 'viewport'
        ? `${query.radiusNm}nm around map center`
        : 'global sample';
    return mapsJson({
      pins,
      count: pins.length,
      empty: pins.length === 0,
      source: fetched.source,
      attribution,
      coverage,
      observedAt,
      stale: false,
      message:
        pins.length === 0
          ? query.mode === 'viewport'
            ? 'No aircraft in this view. Zoom or pan to a busier area.'
            : 'No aircraft in the Maps sample regions.'
          : undefined,
    });
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'Flights fetch failed',
        pins: [],
        count: 0,
        empty: true,
        source: 'flights',
      },
      { status: 502 },
    );
  }
}
