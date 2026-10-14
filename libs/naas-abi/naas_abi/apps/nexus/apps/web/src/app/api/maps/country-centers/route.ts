import { NextResponse } from 'next/server';

import { mapsUpstreamGet } from '../_lib';
import { compactCountryCenters, type CountryCenterRow } from './centers';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** Natural Earth 50m countries: small states included (Singapore, Malta, Bahrain…). */
const NATURAL_EARTH_50M =
  'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson';

let cached: CountryCenterRow[] | null = null;

/**
 * Country label points, names and continents for group-by-country / continent.
 * The 3 MB source is reduced to a few KB once per server process.
 */
export async function GET() {
  try {
    if (!cached) {
      const res = await mapsUpstreamGet(NATURAL_EARTH_50M, { timeoutMs: 30000 });
      if (!res.ok) {
        return NextResponse.json({ error: `Natural Earth ${res.status}` }, { status: 502 });
      }
      cached = compactCountryCenters(await res.json());
    }
    return NextResponse.json(
      { countries: cached },
      { headers: { 'Cache-Control': 'public, max-age=86400' } },
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Natural Earth unavailable';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
