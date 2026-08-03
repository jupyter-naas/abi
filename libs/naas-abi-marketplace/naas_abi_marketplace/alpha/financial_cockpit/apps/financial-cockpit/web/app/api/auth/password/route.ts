import { NextResponse } from 'next/server';

import { verifyPassword } from '@/lib/auth/password';
import { createSessionToken, setSessionCookie } from '@/lib/auth/session';
import { logLogin } from '@/lib/server/analytics';
import {
  checkRateLimit,
  clientKeyFromRequest,
  resetRateLimit,
} from '@/lib/server/rateLimit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * One shared password guards the whole dataset, so unlimited guessing is the
 * cheapest attack on this app. See rateLimit.ts for why this needs an edge rule
 * behind it as well.
 */
const LOGIN_RATE_LIMIT = { limit: 10, windowMs: 10 * 60 * 1000 };

/**
 * Secondary sign-in: a single shared admin password grants a full-access
 * session. Mirrors the magic-link verify route's response shape
 * (`{ ok, redirectTo }`) so the client redirects the same way.
 */
export async function POST(request: Request) {
  const rateKey = `login:${clientKeyFromRequest(request)}`;
  const rate = checkRateLimit(rateKey, LOGIN_RATE_LIMIT);
  if (!rate.allowed) {
    return NextResponse.json(
      { error: 'Trop de tentatives. Réessayez plus tard.' },
      { status: 429, headers: { 'Retry-After': String(rate.retryAfterSeconds) } },
    );
  }

  let body: { password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 });
  }

  const password = body.password ?? '';
  if (!password) {
    return NextResponse.json({ error: 'Mot de passe requis.' }, { status: 400 });
  }

  const payload = verifyPassword(password);
  if (!payload) {
    return NextResponse.json({ error: 'Mot de passe incorrect.' }, { status: 401 });
  }

  // Successful sign-in clears the counter so a legitimate user who fat-fingered
  // the password a few times isn't locked out for the rest of the window.
  resetRateLimit(rateKey);

  const token = await createSessionToken(payload);
  await setSessionCookie(token);
  await logLogin(payload);
  // Land on the default perimeter (resolved by the home route), not /admin.
  return NextResponse.json({ ok: true, redirectTo: '/' });
}
