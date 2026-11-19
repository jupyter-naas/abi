import { NextRequest, NextResponse } from 'next/server';

import { fetchPublic } from '@/lib/public-fetch';
import { requireSignedIn } from '@/lib/web-pass-server';

/**
 * Open Graph tags of a public page, for a signed-in user: fetched from the
 * public internet only (`lib/public-fetch.ts`), at most 512 KB of HTML.
 */

const FETCH_TIMEOUT_MS = 4000;
const MAX_PAGE_BYTES = 512 * 1024;

/** Extract Open Graph meta tags from HTML string */
function extractOg(html: string): { title?: string; description?: string; image?: string } {
  const result: { title?: string; description?: string; image?: string } = {};
  const ogTitle = html.match(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']/i)
    || html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:title["']/i);
  if (ogTitle) result.title = ogTitle[1].trim();
  const ogDesc = html.match(/<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']+)["']/i)
    || html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:description["']/i);
  if (ogDesc) result.description = ogDesc[1].trim();
  const ogImage = html.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i)
    || html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i);
  if (ogImage) result.image = ogImage[1].trim();
  return result;
}

export async function GET(request: NextRequest) {
  const gate = await requireSignedIn(request);
  if (gate.refused) return gate.refused;
  const url = request.nextUrl.searchParams.get('url');
  if (!url || !/^https:\/\//i.test(url)) {
    return NextResponse.json({ error: 'Invalid url' }, { status: 400 });
  }
  try {
    const res = await fetchPublic(url, {
      maxBytes: MAX_PAGE_BYTES,
      timeoutMs: FETCH_TIMEOUT_MS,
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; NexusLinkPreview/1.0)', Accept: 'text/html' },
    });
    const isHtml = /^text\/html\b|^application\/xhtml\+xml\b/i.test(res.contentType);
    if (res.status < 200 || res.status >= 300 || !isHtml) return NextResponse.json(extractOg(''), { status: 200 });
    return NextResponse.json(extractOg(res.body.toString('utf8')));
  } catch {
    return NextResponse.json({ title: undefined, description: undefined, image: undefined }, { status: 200 });
  }
}
