import { NextResponse } from 'next/server';

/** Maps-owned upstream identity (NWS and similar require a contactable UA). */
export const MAPS_USER_AGENT =
  'NexusMaps/1.0 (+https://zen.naas.ai; maps@naas.ai)';

export function mapsJson(
  body: unknown,
  init?: { status?: number; cacheSeconds?: number },
): NextResponse {
  const status = init?.status ?? 200;
  const cacheSeconds = init?.cacheSeconds ?? 60;
  const cacheControl =
    cacheSeconds <= 0
      ? 'private, no-store'
      : `public, max-age=${cacheSeconds}, stale-while-revalidate=30`;
  return NextResponse.json(body, {
    status,
    headers: {
      'Cache-Control': cacheControl,
    },
  });
}

export async function mapsUpstreamGet(
  url: string,
  init?: {
    headers?: Record<string, string>;
    timeoutMs?: number;
  },
): Promise<Response> {
  return fetch(url, {
    headers: {
      Accept: 'application/json, application/geo+json, application/xml, text/xml, */*',
      'User-Agent': MAPS_USER_AGENT,
      ...(init?.headers ?? {}),
    },
    signal: AbortSignal.timeout(init?.timeoutMs ?? 20000),
    cache: 'no-store',
  });
}

export function mapsPinResponse(
  pins: Array<Record<string, unknown>>,
  meta: Record<string, unknown> = {},
): NextResponse {
  return mapsJson({ pins, count: pins.length, ...meta });
}
