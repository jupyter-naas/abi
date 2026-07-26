import { NextRequest, NextResponse } from 'next/server';

import { mapsJson, MAPS_USER_AGENT } from '../_lib';
import {
  getFirmsWmsUrl,
  resolveFirmsMapKey,
} from '@/app/workspace/[workspaceId]/maps/lib/firms';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * NASA FIRMS VIIRS WMS proxy.
 *
 * FIRMS requires a free MAP_KEY in the WMS path. Without a configured key the
 * upstream returns tiles reading "MAP_KEY is invalid…", which covers the map.
 *
 * - GET ?status=1 → { enabled, source } (no secret)
 * - GET with WMS REQUEST=GetMap → tile proxy when FIRMS_MAP_KEY is set
 */
export async function GET(req: NextRequest) {
  const key = resolveFirmsMapKey(
    process.env.FIRMS_MAP_KEY ?? process.env.NEXT_PUBLIC_FIRMS_MAP_KEY,
  );
  const url = new URL(req.url);
  // Leaflet WMS uses lowercase `request=GetMap`; treat any request/REQUEST as tile.
  const wmsRequest =
    url.searchParams.get('REQUEST') ?? url.searchParams.get('request');
  const wantsStatus =
    url.searchParams.get('status') === '1' || !wmsRequest;

  if (wantsStatus) {
    return mapsJson(
      {
        enabled: Boolean(key),
        source: key ? 'firms-wms' : 'eonet-only',
        note: key
          ? 'FIRMS WMS overlay available.'
          : 'FIRMS_MAP_KEY unset; Wildfires canvas uses EONET named incidents only.',
      },
      { cacheSeconds: 60 },
    );
  }

  if (!key) {
    return NextResponse.json(
      {
        error: 'FIRMS_MAP_KEY unset',
        note: 'Set FIRMS_MAP_KEY (or NEXT_PUBLIC_FIRMS_MAP_KEY) on nexus-web to enable VIIRS WMS.',
      },
      { status: 503 },
    );
  }

  const upstreamBase = getFirmsWmsUrl(key);
  if (!upstreamBase) {
    return NextResponse.json({ error: 'Invalid FIRMS_MAP_KEY' }, { status: 503 });
  }

  const upstream = new URL(upstreamBase);
  url.searchParams.forEach((value, name) => {
    if (name === 'status') return;
    upstream.searchParams.set(name, value);
  });

  try {
    const res = await fetch(upstream.toString(), {
      headers: { 'User-Agent': MAPS_USER_AGENT },
      signal: AbortSignal.timeout(25000),
      cache: 'no-store',
    });
    const contentType =
      res.headers.get('Content-Type') ?? 'application/octet-stream';
    return new NextResponse(res.body, {
      status: res.status,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=120, stale-while-revalidate=60',
      },
    });
  } catch (err) {
    return NextResponse.json(
      {
        error: err instanceof Error ? err.message : 'FIRMS upstream failed',
      },
      { status: 502 },
    );
  }
}
