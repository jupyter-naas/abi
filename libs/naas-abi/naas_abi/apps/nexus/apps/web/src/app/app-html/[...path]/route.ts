import { NextRequest, NextResponse } from 'next/server';

const UPSTREAM =
  process.env.NEXUS_INTERNAL_API_URL ??
  process.env.NEXUS_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  'http://localhost:9879';

const APP_HTML_TOKEN_COOKIE = 'abi_app_html_token';

/** Request headers the upstream needs to read the body and choose a response format. */
const FORWARDED_REQUEST_HEADERS = ['content-type', 'accept', 'range', 'if-none-match', 'if-modified-since'];

/** Response headers the browser gets from the upstream. */
const RETURNED_RESPONSE_HEADERS = [
  'content-type',
  'content-disposition',
  'content-range',
  'accept-ranges',
  'cache-control',
  'etag',
  'last-modified',
  'location',
  'set-cookie',
  'www-authenticate',
  'content-security-policy',
  'referrer-policy',
  'x-content-type-options',
];

/**
 * Where browsers reach the API. A remote module's app is served there, under
 * a grant, never from this origin: the redirect of ``/app-html/remote/`` to
 * ``/app-remote/<grant>/`` is pointed at it.
 */
function publicApiBase(): string | null {
  const url = process.env.NEXUS_API_URL ?? process.env.NEXT_PUBLIC_API_URL;
  return url ? url.replace(/\/+$/, '') : null;
}

/**
 * Forward caller credentials only — never forge ``ABI_API_KEY``.
 * Accepts Authorization, ``?token=``, or the scoped app-html cookie.
 * The content type is forwarded too: without it a multipart body loses its
 * boundary and the upstream cannot read any form field.
 */
function upstreamHeaders(request: NextRequest): HeadersInit {
  const headers: Record<string, string> = {};
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
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

/** A redirect to a remote app's grant URL goes to the API's origin. */
function browserLocation(location: string, apiBase: string | null): string {
  if (apiBase && location.startsWith('/app-remote/')) {
    return `${apiBase}${location}`;
  }
  return location;
}

/**
 * Proxy bundled Nexus app HTML from the API so iframes load same-origin.
 * Upstream ``/app-html/`` requires a real JWT / cookie — anonymous requests
 * without ``?token=`` receive 401.
 *
 * Bodies stream both ways (uploads, downloads, server-sent events), and a
 * redirect reaches the browser as the upstream sent it, never followed here.
 * ``/app-html/remote/<module>/<app>/`` is forwarded too: the upstream answers
 * it with a redirect to the app's grant URL on the API origin.
 */
async function proxy(request: NextRequest, params: { path: string[] }) {
  const subpath = params.path.join('/');
  const qs = request.nextUrl.search;
  const target = `${UPSTREAM.replace(/\/$/, '')}/app-html/${subpath}${qs}`;

  try {
    // ``duplex`` lets fetch send a streamed body (Node); not in the DOM types.
    const init: RequestInit & { duplex?: 'half' } = {
      method: request.method,
      headers: upstreamHeaders(request),
      cache: 'no-store',
      redirect: 'manual',
    };
    if (request.method !== 'GET' && request.method !== 'HEAD' && request.body) {
      init.body = request.body;
      init.duplex = 'half';
    }
    const res = await fetch(target, init);
    const headers = new Headers();
    for (const name of RETURNED_RESPONSE_HEADERS) {
      // set-cookie may appear multiple times; Headers#get joins — prefer getSetCookie when available.
      if (name === 'set-cookie' && typeof res.headers.getSetCookie === 'function') {
        for (const cookie of res.headers.getSetCookie()) {
          headers.append('set-cookie', cookie);
        }
        continue;
      }
      const value = res.headers.get(name);
      if (!value) continue;
      headers.set(name, name === 'location' ? browserLocation(value, publicApiBase()) : value);
    }
    // fetch decodes a compressed body: its length is then not the one sent.
    const length = res.headers.get('content-length');
    if (length && !res.headers.get('content-encoding')) {
      headers.set('content-length', length);
    }
    return new NextResponse(res.body, { status: res.status, headers });
  } catch {
    return NextResponse.json({ error: 'upstream unreachable' }, { status: 502 });
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await params);
}

export async function HEAD(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await params);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await params);
}
