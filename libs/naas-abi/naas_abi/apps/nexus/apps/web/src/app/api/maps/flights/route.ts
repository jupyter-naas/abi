import { mapsJson } from '../_lib';
import {
  collectFlightPins,
  parseFlightsQuery,
  sampleAircraft,
  viewportAircraft,
} from './flights';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

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
