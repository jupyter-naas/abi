import { NextResponse } from 'next/server';

import { WEB_PASS_COOKIE, WEB_PASS_UNTIL_COOKIE } from '@/lib/web-pass';
import { checkWebPass, cookieOf, forgetWebPasses } from '@/lib/web-pass-server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * This host's web pass (`lib/web-pass.ts`, `lib/web-pass-server.ts`).
 *
 * - GET: whether the request holds a live pass, and how long it lasts (asked of
 *   the API, never from a kept answer: a pass revoked elsewhere reads as gone);
 * - POST `{ web_pass }`: keep a live pass as an httpOnly, SameSite=Strict cookie,
 *   with its readable twin `WEB_PASS_UNTIL_COOKIE` (when it ends);
 * - DELETE: drop both.
 *
 * Only this app's own pages may set or drop it (`Sec-Fetch-Site`, else `Origin`).
 */

const NO_STORE = { 'Cache-Control': 'private, no-store' };

function ownHost(request: Request): string {
  return request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? new URL(request.url).host;
}

function isHttps(request: Request): boolean {
  const forwarded = request.headers.get('x-forwarded-proto');
  if (forwarded) return forwarded.split(',')[0].trim() === 'https';
  return new URL(request.url).protocol === 'https:';
}

/**
 * A request this app's own pages made: never another site's form or script. A
 * browser's `Sec-Fetch-Site` says so on its own (a proxy may rewrite `Host`);
 * without it, the `Origin` host must be this one.
 */
function fromThisApp(request: Request): boolean {
  const site = request.headers.get('sec-fetch-site');
  if (site) return site === 'same-origin';
  const origin = request.headers.get('origin');
  if (!origin) return true;
  try {
    return new URL(origin).host === ownHost(request);
  } catch {
    return false;
  }
}

function cookieHeader(
  request: Request,
  name: string,
  value: string,
  maxAge: number,
  { httpOnly }: { httpOnly: boolean },
): string {
  const parts = [
    `${name}=${encodeURIComponent(value)}`,
    'Path=/',
    `Max-Age=${Math.max(0, Math.floor(maxAge))}`,
    'SameSite=Strict',
  ];
  if (httpOnly) parts.push('HttpOnly');
  if (isHttps(request)) parts.push('Secure');
  return parts.join('; ');
}

/** The pass cookie and its readable twin, set (`expiresIn` > 0) or cleared. */
function passCookies(request: Request, value: string, expiresIn: number): Headers {
  const headers = new Headers(NO_STORE);
  const until = expiresIn > 0 ? String(Math.floor(Date.now() / 1000) + Math.floor(expiresIn)) : '';
  headers.append('Set-Cookie', cookieHeader(request, WEB_PASS_COOKIE, value, expiresIn, { httpOnly: true }));
  headers.append('Set-Cookie', cookieHeader(request, WEB_PASS_UNTIL_COOKIE, until, expiresIn, { httpOnly: false }));
  return headers;
}

export async function GET(request: Request) {
  const held = cookieOf(request, WEB_PASS_COOKIE);
  if (held) forgetWebPasses(held);
  const holder = await checkWebPass(held);
  return NextResponse.json(
    holder ? { active: true, expires_in: holder.expiresIn } : { active: false },
    { headers: NO_STORE },
  );
}

export async function POST(request: Request) {
  if (!fromThisApp(request)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403, headers: NO_STORE });
  }
  let value: unknown;
  try {
    value = ((await request.json()) as { web_pass?: unknown })?.web_pass;
  } catch {
    value = undefined;
  }
  if (typeof value !== 'string') {
    return NextResponse.json({ error: 'web_pass required' }, { status: 400, headers: NO_STORE });
  }
  forgetWebPasses(value);
  const holder = await checkWebPass(value);
  if (!holder) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401, headers: NO_STORE });
  }
  return NextResponse.json(
    { active: true, expires_in: holder.expiresIn },
    { headers: passCookies(request, value, holder.expiresIn) },
  );
}

export async function DELETE(request: Request) {
  if (!fromThisApp(request)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403, headers: NO_STORE });
  }
  const held = cookieOf(request, WEB_PASS_COOKIE);
  if (held) forgetWebPasses(held);
  return NextResponse.json({ active: false }, { headers: passCookies(request, '', 0) });
}
