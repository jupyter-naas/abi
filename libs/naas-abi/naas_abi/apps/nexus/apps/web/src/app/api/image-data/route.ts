import { NextResponse } from 'next/server';
import { readLocalImage } from '@/lib/local-image-file';
import { fetchPublic, PublicFetchRefused } from '@/lib/public-fetch';
import { requireSignedIn } from '@/lib/web-pass-server';

export const runtime = 'nodejs';

/**
 * An image for a signed-in user's page: a repository image, or a remote one
 * fetched from the public internet only (`lib/public-fetch.ts`). A remote
 * answer is served only as a raster image. Every image goes out with
 * `nosniff` and a sandboxing CSP, so nothing served here runs as this app.
 */

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const FETCH_TIMEOUT_MS = 8_000;

/** Image types served from a remote answer: rasters only, never SVG or anything active. */
const RASTER_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'image/avif',
  'image/bmp',
  'image/x-icon',
  'image/vnd.microsoft.icon',
]);

const IMAGE_RESPONSE_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; sandbox",
  'Content-Disposition': 'inline',
  'Cache-Control': 'private, max-age=3600',
} as const;

function toBase64(data: ArrayBuffer | Buffer): string {
  const bytes = data instanceof ArrayBuffer ? new Uint8Array(data) : data;
  return Buffer.from(bytes).toString('base64');
}

function asImageResponse(bytes: Buffer, contentType: string, raw: boolean) {
  if (raw) {
    return new NextResponse(new Uint8Array(bytes), {
      headers: { 'Content-Type': contentType, ...IMAGE_RESPONSE_HEADERS },
    });
  }
  return NextResponse.json(
    { dataUri: `data:${contentType};base64,${toBase64(bytes)}` },
    { headers: { 'Cache-Control': 'private, max-age=3600' } },
  );
}

function rasterType(contentType: string): string | null {
  const type = contentType.split(';')[0].trim().toLowerCase();
  return RASTER_TYPES.has(type) ? type : null;
}

export async function GET(request: Request) {
  const gate = await requireSignedIn(request);
  if (gate.refused) return gate.refused;

  const { searchParams } = new URL(request.url);
  const url = searchParams.get('url');
  const raw = searchParams.get('raw') === '1';

  if (!url) {
    return NextResponse.json({ error: 'Missing url' }, { status: 400 });
  }

  const local = readLocalImage(url);
  if (local) {
    return asImageResponse(local.bytes, local.contentType, raw);
  }

  if (!/^https:\/\//i.test(url)) {
    return NextResponse.json({ error: 'Image not found' }, { status: 404 });
  }

  try {
    const res = await fetchPublic(url, {
      maxBytes: MAX_IMAGE_BYTES,
      timeoutMs: FETCH_TIMEOUT_MS,
      headers: { Accept: 'image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8' },
    });
    if (res.status < 200 || res.status >= 300) {
      return NextResponse.json({ error: `Upstream error (${res.status})` }, { status: 502 });
    }
    const type = rasterType(res.contentType);
    if (!type) {
      return NextResponse.json({ error: 'Not an image' }, { status: 415 });
    }
    return asImageResponse(res.body, type, raw);
  } catch (error) {
    if (error instanceof PublicFetchRefused) {
      return NextResponse.json({ error: error.message }, { status: 400 });
    }
    return NextResponse.json({ error: 'Failed to fetch image' }, { status: 502 });
  }
}
