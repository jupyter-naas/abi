import { NextRequest, NextResponse } from 'next/server';

const UPSTREAM =
  process.env.NEXUS_INTERNAL_API_URL ??
  process.env.NEXUS_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  'http://localhost:9879';

/**
 * Proxy bundled Nexus app HTML from the API so iframes load same-origin.
 * (Catalog apps use /app-html/<module>/<app>/… paths.)
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const subpath = params.path.join('/');
  const qs = request.nextUrl.search;
  const target = `${UPSTREAM.replace(/\/$/, '')}/app-html/${subpath}${qs}`;

  try {
    const res = await fetch(target, { cache: 'no-store' });
    const body = await res.arrayBuffer();
    const headers = new Headers();
    const contentType = res.headers.get('content-type');
    if (contentType) {
      headers.set('content-type', contentType);
    }
    const etag = res.headers.get('etag');
    if (etag) {
      headers.set('etag', etag);
    }
    const lastModified = res.headers.get('last-modified');
    if (lastModified) {
      headers.set('last-modified', lastModified);
    }
    return new NextResponse(body, { status: res.status, headers });
  } catch {
    return NextResponse.json({ error: 'upstream unreachable' }, { status: 502 });
  }
}
