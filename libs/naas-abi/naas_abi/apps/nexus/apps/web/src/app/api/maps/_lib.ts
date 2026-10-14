import { NextResponse } from 'next/server';

import {
  buildMapsFeedPayload,
  isMapsFeatureCollection,
} from '@/app/workspace/[workspaceId]/maps/lib/maps-pin-geojson';

/** Server-side ABI base URL (Docker compose uses NEXUS_INTERNAL_API_URL). */
export function nexusInternalApiBase(): string {
  const configured =
    process.env.NEXUS_INTERNAL_API_URL ??
    process.env.NEXUS_API_URL ??
    process.env.NEXT_PUBLIC_API_URL;
  if (configured?.startsWith('http')) return configured.replace(/\/$/, '');
  if (configured) return `http://${configured.replace(/\/$/, '')}`;
  return 'http://localhost:9879';
}

/** Maps-owned upstream identity (NWS and similar require a contactable UA). */
export const MAPS_USER_AGENT =
  'NexusMaps/1.0 (+https://naas.ai; maps@naas.ai)';

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
  init?: { status?: number; cacheSeconds?: number },
): NextResponse {
  return mapsJson(buildMapsFeedPayload(pins, meta), init);
}

/** Merge upstream feed JSON into a Maps GeoJSON FeatureCollection response. */
export function mapsFeedResponse(
  body: unknown,
  init?: { status?: number; cacheSeconds?: number },
): NextResponse {
  if (isMapsFeatureCollection(body)) {
    const record = body as Record<string, unknown>;
    const count =
      typeof record.count === 'number'
        ? record.count
        : body.features.length;
    return mapsJson({ ...record, count }, init);
  }
  const record =
    body && typeof body === 'object'
      ? (body as Record<string, unknown>)
      : {};
  const pins = Array.isArray(record.pins)
    ? (record.pins as Array<Record<string, unknown>>)
    : [];
  const meta = { ...record };
  delete meta.pins;
  return mapsJson(buildMapsFeedPayload(pins, meta), init);
}
