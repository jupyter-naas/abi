import { NextRequest, NextResponse } from 'next/server';

import { resolveGoogleMapsApiKey } from '../../_google';
import { MAPS_USER_AGENT, mapsJson } from '../../_lib';
import { parsePlacePhotoRef, placePhotoUpstreamUrl } from './photo';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const resolved = resolveGoogleMapsApiKey();
  if (!resolved) {
    return mapsJson({ error: 'Places key unset' }, { status: 503 });
  }
  const ref = parsePlacePhotoRef(new URL(req.url).searchParams.get('ref'));
  if (!ref) {
    return mapsJson({ error: 'photo reference required' }, { status: 400 });
  }
  try {
    const res = await fetch(placePhotoUpstreamUrl(ref, resolved.key), {
      headers: { 'User-Agent': MAPS_USER_AGENT, Accept: 'image/*' },
      signal: AbortSignal.timeout(15000),
      cache: 'no-store',
      redirect: 'follow',
    });
    const contentType = res.headers.get('Content-Type') ?? 'image/jpeg';
    if (!res.ok || !contentType.startsWith('image/')) {
      return mapsJson({ error: 'Place photo unavailable' }, { status: 502 });
    }
    return new NextResponse(res.body, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=86400, stale-while-revalidate=3600',
        'X-Maps-Preview-Source': 'places',
      },
    });
  } catch (err) {
    return mapsJson(
      { error: err instanceof Error ? err.message : 'Place photo failed' },
      { status: 502 },
    );
  }
}
