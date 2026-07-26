import { NextResponse } from 'next/server';

export const MAPS_PROXY_UA = 'NexusMaps/1.0 (+https://naas.ai; situation-awareness)';

export async function mapsUpstreamGet(
  url: string,
  init?: {
    headers?: Record<string, string>;
    timeoutMs?: number;
    cacheSeconds?: number;
  },
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    init?.timeoutMs ?? 20000,
  );
  try {
    return await fetch(url, {
      signal: controller.signal,
      headers: {
        Accept: 'application/json, application/geo+json, text/xml, */*',
        'User-Agent': MAPS_PROXY_UA,
        ...(init?.headers ?? {}),
      },
      next: init?.cacheSeconds
        ? { revalidate: init.cacheSeconds }
        : undefined,
    });
  } finally {
    clearTimeout(timeout);
  }
}

export function mapsJson(
  body: unknown,
  init?: { status?: number; cacheSeconds?: number },
): NextResponse {
  const cacheSeconds = init?.cacheSeconds ?? 60;
  return NextResponse.json(body, {
    status: init?.status ?? 200,
    headers: {
      'Cache-Control': `public, s-maxage=${cacheSeconds}, stale-while-revalidate=${cacheSeconds * 2}`,
    },
  });
}

export function mapsProxyError(message: string, status = 502): NextResponse {
  return mapsJson({ error: message, pins: [] }, { status, cacheSeconds: 15 });
}
