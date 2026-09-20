import { NextRequest, NextResponse } from 'next/server';

import { resolveGoogleMapsApiKey } from '../_google';
import { MAPS_USER_AGENT, mapsJson } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export { resolveGoogleMapsApiKey } from '../_google';

const DEFAULT_SIZE = { width: 640, height: 320 };
const MAX_SIZE = { width: 640, height: 640 };
const OSM_ZOOM = 17;

export type StreetViewQuery = {
  lat: number;
  lng: number;
  width: number;
  height: number;
};

export function parseStreetViewQuery(
  params: URLSearchParams,
): StreetViewQuery | null {
  if (!params.has('lat') || !params.has('lng')) return null;
  const lat = Number(params.get('lat'));
  const lng = Number(params.get('lng'));
  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng) ||
    Math.abs(lat) > 90 ||
    Math.abs(lng) > 180
  ) {
    return null;
  }
  const raw = params.get('size') ?? '';
  const match = /^(\d{2,4})x(\d{2,4})$/.exec(raw);
  const width = match
    ? Math.min(MAX_SIZE.width, Math.max(64, Number(match[1])))
    : DEFAULT_SIZE.width;
  const height = match
    ? Math.min(MAX_SIZE.height, Math.max(64, Number(match[2])))
    : DEFAULT_SIZE.height;
  return { lat, lng, width, height };
}

export function googleStreetViewStaticUrl(
  query: StreetViewQuery,
  key: string,
): string {
  const url = new URL('https://maps.googleapis.com/maps/api/streetview');
  url.searchParams.set('size', `${query.width}x${query.height}`);
  url.searchParams.set('location', `${query.lat},${query.lng}`);
  url.searchParams.set('fov', '80');
  url.searchParams.set('pitch', '0');
  url.searchParams.set('key', key);
  return url.toString();
}

export function lonLatToTile(
  lat: number,
  lng: number,
  zoom: number,
): { x: number; y: number; px: number; py: number } {
  const n = 2 ** zoom;
  const x = ((lng + 180) / 360) * n;
  const latRad = (lat * Math.PI) / 180;
  const y =
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) *
    n;
  return {
    x: Math.floor(x),
    y: Math.floor(y),
    px: (x - Math.floor(x)) * 256,
    py: (y - Math.floor(y)) * 256,
  };
}

export function osmTileUrl(zoom: number, x: number, y: number): string {
  const n = 2 ** zoom;
  const wrappedX = ((x % n) + n) % n;
  const clampedY = Math.min(n - 1, Math.max(0, y));
  return `https://tile.openstreetmap.org/${zoom}/${wrappedX}/${clampedY}.png`;
}

export function placeholderPreviewSvg(
  query: StreetViewQuery,
  reason: string,
): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${query.width}" height="${query.height}" viewBox="0 0 ${query.width} ${query.height}" role="img">
  <rect width="100%" height="100%" fill="#c5d0d8"/>
  <circle cx="${query.width / 2}" cy="${query.height / 2}" r="10" fill="#2563eb" stroke="#ffffff" stroke-width="3"/>
  <text x="50%" y="78%" text-anchor="middle" font-size="12" fill="#334155">${escapeXml(reason)}</text>
</svg>`;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function isPng(bytes: Uint8Array): boolean {
  return (
    bytes.length > 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  );
}

function isJpeg(bytes: Uint8Array): boolean {
  return bytes.length > 3 && bytes[0] === 0xff && bytes[1] === 0xd8;
}

function imageResponse(
  body: BodyInit,
  contentType: string,
  source: string,
): NextResponse {
  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'public, max-age=3600, stale-while-revalidate=600',
      'X-Maps-Preview-Source': source,
    },
  });
}

async function fetchBytes(url: string, timeoutMs = 12000): Promise<Uint8Array | null> {
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': MAPS_USER_AGENT, Accept: 'image/*,*/*' },
      signal: AbortSignal.timeout(timeoutMs),
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return new Uint8Array(await res.arrayBuffer());
  } catch {
    return null;
  }
}

async function googlePreview(
  query: StreetViewQuery,
  key: string,
): Promise<NextResponse | null> {
  const bytes = await fetchBytes(googleStreetViewStaticUrl(query, key));
  if (!bytes) return null;
  if (isJpeg(bytes)) {
    return imageResponse(Buffer.from(bytes), 'image/jpeg', 'google-streetview');
  }
  if (isPng(bytes)) {
    return imageResponse(Buffer.from(bytes), 'image/png', 'google-streetview');
  }
  return null;
}

function tilePreviewSvg(
  query: StreetViewQuery,
  tile: { px: number; py: number },
  png: Uint8Array,
): string {
  const href = `data:image/png;base64,${Buffer.from(png).toString('base64')}`;
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${query.width}" height="${query.height}" viewBox="0 0 256 256" role="img">
  <image x="0" y="0" width="256" height="256" preserveAspectRatio="xMidYMid slice" href="${href}" xlink:href="${href}"/>
  <circle cx="${tile.px.toFixed(1)}" cy="${tile.py.toFixed(1)}" r="8" fill="#ea8a23" stroke="#ffffff" stroke-width="2"/>
</svg>`;
}

async function osmPreview(query: StreetViewQuery): Promise<NextResponse> {
  const tile = lonLatToTile(query.lat, query.lng, OSM_ZOOM);
  const bytes = await fetchBytes(osmTileUrl(OSM_ZOOM, tile.x, tile.y));
  if (bytes && isPng(bytes)) {
    return imageResponse(
      tilePreviewSvg(query, tile, bytes),
      'image/svg+xml; charset=utf-8',
      'openstreetmap',
    );
  }
  return imageResponse(
    placeholderPreviewSvg(query, 'Location preview'),
    'image/svg+xml; charset=utf-8',
    'placeholder',
  );
}

/** Same-origin pin preview. Google Street View Static when a server key exists. */
export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  if (url.searchParams.get('status') === '1') {
    const resolved = resolveGoogleMapsApiKey();
    return mapsJson(
      {
        enabled: true,
        source: resolved ? 'google-streetview' : 'openstreetmap',
        keyed: Boolean(resolved),
      },
      { cacheSeconds: 60 },
    );
  }

  const query = parseStreetViewQuery(url.searchParams);
  if (!query) {
    return mapsJson({ error: 'lat and lng are required' }, { status: 400 });
  }

  const resolved = resolveGoogleMapsApiKey();
  if (resolved) {
    const google = await googlePreview(query, resolved.key);
    if (google) return google;
  }
  return osmPreview(query);
}
