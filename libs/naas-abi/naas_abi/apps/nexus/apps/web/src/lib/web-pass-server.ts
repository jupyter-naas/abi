/**
 * Who is signed in, for the web app's own server routes (`/api/image-data`,
 * `/api/link-preview`, `/api/maps/*`).
 *
 * The API's session cookie stays on the API's host, which is usually not this
 * one, so these routes never see it. The browser asks the API for a web pass
 * (`lib/web-pass.ts`) and hands it to `POST /api/web-pass`, which keeps it in
 * the httpOnly cookie `WEB_PASS_COOKIE` of this host. Each route asks the API
 * whose pass it is (`GET /api/auth/oidc/web-pass`), and keeps the answer for at
 * most a minute. A request without a live pass names nobody.
 */

import { NextResponse } from 'next/server';

import { nexusInternalApiBase } from '@/lib/internal-api';
import { WEB_PASS_COOKIE } from '@/lib/web-pass';

export const WEB_PASS_HEADER = 'X-Web-Pass';

/** A pass is an IAM grant (`abi_gk_<id>_<secret>`): anything else names nobody. */
const PASS_PATTERN = /^abi_gk_[A-Za-z0-9_-]{1,500}$/;
const KEEP_LIVE_MS = 60_000;
const KEEP_REFUSED_MS = 10_000;
const MAX_KEPT = 2_000;

export type WebPassHolder = { userId: string; expiresIn: number };

type Kept = { holder: WebPassHolder | null; until: number };
const kept = new Map<string, Kept>();

/** Forget every answer kept (tests, and a pass dropped at sign-out). */
export function forgetWebPasses(value?: string): void {
  if (value === undefined) kept.clear();
  else kept.delete(value);
}

function keep(value: string, holder: WebPassHolder | null, ms: number): void {
  if (kept.size >= MAX_KEPT) {
    const oldest = kept.keys().next().value;
    if (oldest !== undefined) kept.delete(oldest);
  }
  kept.set(value, { holder, until: Date.now() + ms });
}

/** The value of one cookie of a request, read from its `Cookie` header. */
export function cookieOf(request: Request, name: string): string | null {
  const header = request.headers.get('cookie');
  if (!header) return null;
  for (const part of header.split(';')) {
    const at = part.indexOf('=');
    if (at < 0) continue;
    if (part.slice(0, at).trim() !== name) continue;
    const value = part.slice(at + 1).trim();
    try {
      return decodeURIComponent(value);
    } catch {
      return null;
    }
  }
  return null;
}

export function isWebPassShaped(value: string | null | undefined): value is string {
  return typeof value === 'string' && PASS_PATTERN.test(value);
}

/** Whose pass `value` is, asked of the API; null for anything but a live pass. */
export async function checkWebPass(value: string | null | undefined): Promise<WebPassHolder | null> {
  if (!isWebPassShaped(value)) return null;
  const known = kept.get(value);
  if (known && known.until > Date.now()) return known.holder;
  let holder: WebPassHolder | null = null;
  try {
    const res = await fetch(`${nexusInternalApiBase()}/api/auth/oidc/web-pass`, {
      headers: { [WEB_PASS_HEADER]: value },
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(5_000),
    });
    if (res.status === 401) {
      // The API refused the pass: kept as a refusal for a moment.
    } else if (!res.ok) {
      // The API could not say (restarting, busy): nobody now, and nothing is kept.
      return null;
    } else {
      const body = (await res.json()) as { user_id?: unknown; expires_in?: unknown };
      if (typeof body.user_id === 'string' && body.user_id && typeof body.expires_in === 'number') {
        holder = { userId: body.user_id, expiresIn: body.expires_in };
      }
    }
  } catch {
    // The API did not answer: nobody is signed in, and nothing is kept.
    return null;
  }
  keep(
    value,
    holder,
    holder ? Math.min(KEEP_LIVE_MS, Math.max(0, holder.expiresIn * 1000)) : KEEP_REFUSED_MS,
  );
  return holder;
}

/** Who sent `request`: the holder of its web pass cookie, or null. */
export async function signedInUser(request: Request): Promise<WebPassHolder | null> {
  return checkWebPass(cookieOf(request, WEB_PASS_COOKIE));
}

export function notSignedIn(): NextResponse {
  return NextResponse.json(
    { error: 'Not authenticated' },
    { status: 401, headers: { 'Cache-Control': 'private, no-store' } },
  );
}

/** The holder of the request's pass, or the 401 to answer with. */
export async function requireSignedIn(
  request: Request,
): Promise<{ user: WebPassHolder; refused?: undefined } | { user?: undefined; refused: NextResponse }> {
  const user = await signedInUser(request);
  return user ? { user } : { refused: notSignedIn() };
}
