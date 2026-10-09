import { NextResponse } from 'next/server';

import { mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const NATURAL_EARTH_COUNTRIES =
  'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson';

/** Natural Earth 110m countries, proxied so the browser does not call GitHub. */
export async function GET() {
  try {
    const res = await mapsUpstreamGet(NATURAL_EARTH_COUNTRIES, { timeoutMs: 20000 });
    if (!res.ok) {
      return NextResponse.json({ error: `Natural Earth ${res.status}` }, { status: 502 });
    }
    return new NextResponse(await res.text(), {
      status: 200,
      headers: {
        'Content-Type': 'application/geo+json',
        'Cache-Control': 'public, max-age=86400',
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Natural Earth unavailable';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
