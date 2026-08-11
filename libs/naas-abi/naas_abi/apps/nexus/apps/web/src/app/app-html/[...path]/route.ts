import { NextRequest, NextResponse } from 'next/server';

const UPSTREAM =
  process.env.NEXUS_INTERNAL_API_URL ??
  process.env.NEXUS_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  'http://localhost:9879';

const APP_HTML_TOKEN_COOKIE = 'abi_app_html_token';

/**
 * Forward caller credentials only — never forge ``ABI_API_KEY``.
 * Accepts Authorization, ``?token=``, or the scoped app-html cookie.
 */
function upstreamHeaders(request: NextRequest): HeadersInit {
  const headers: Record<string, string> = {};
  const incoming = request.headers.get('authorization');
  if (incoming) {
    headers.Authorization = incoming;
  } else {
    const queryToken = request.nextUrl.searchParams.get('token');
    const cookieToken = request.cookies.get(APP_HTML_TOKEN_COOKIE)?.value;
    const token = queryToken || cookieToken;
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  const cookie = request.headers.get('cookie');
  if (cookie) {
    headers.Cookie = cookie;
  }
  return headers;
}

/**
 * Proxy bundled Nexus app HTML from the API so iframes load same-origin.
 * Upstream ``/app-html/`` requires a real JWT / cookie — anonymous requests
 * without ``?token=`` receive 401.
 */
async function proxy(request: NextRequest, params: { path: string[] }) {
  const subpath = params.path.join('/');
  const qs = request.nextUrl.search;
  const target = `${UPSTREAM.replace(/\/$/, '')}/app-html/${subpath}${qs}`;

  try {
    const init: RequestInit = {
      method: request.method,
      headers: upstreamHeaders(request),
      cache: 'no-store',
    };
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      init.body = await request.arrayBuffer();
    }
    const res = await fetch(target, init);
    const body = await res.arrayBuffer();
    const headers = new Headers();
    for (const name of [
      'content-type',
      'content-disposition',
      'cache-control',
      'etag',
      'last-modified',
      'set-cookie',
      'www-authenticate',
    ]) {
      // set-cookie may appear multiple times; Headers#get joins — prefer getSetCookie when available.
      if (name === 'set-cookie' && typeof res.headers.getSetCookie === 'function') {
        for (const cookie of res.headers.getSetCookie()) {
          headers.append('set-cookie', cookie);
        }
        continue;
      }
      const value = res.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new NextResponse(body, { status: res.status, headers });
  } catch {
    return NextResponse.json({ error: 'upstream unreachable' }, { status: 502 });
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxy(request, params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxy(request, params);
}
