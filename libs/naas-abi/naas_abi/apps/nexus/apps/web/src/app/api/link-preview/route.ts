import { NextRequest, NextResponse } from 'next/server';

const FETCH_TIMEOUT_MS = 4000;

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
  const url = request.nextUrl.searchParams.get('url');
  if (!url || !url.startsWith('http')) {
    return NextResponse.json({ error: 'Invalid url' }, { status: 400 });
  }
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; NexusLinkPreview/1.0)' },
    });
    clearTimeout(timeout);
    if (!res.ok) return NextResponse.json(extractOg(''), { status: 200 });
    const html = await res.text();
    const meta = extractOg(html);
    return NextResponse.json(meta);
  } catch {
    return NextResponse.json({ title: undefined, description: undefined, image: undefined }, { status: 200 });
  }
}
