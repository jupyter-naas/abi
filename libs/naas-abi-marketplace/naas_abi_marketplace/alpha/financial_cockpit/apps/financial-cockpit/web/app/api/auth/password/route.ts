import { NextResponse } from 'next/server';

import { verifyPassword } from '@/lib/auth/password';
import { createSessionToken, setSessionCookie } from '@/lib/auth/session';
import { logLogin } from '@/lib/server/analytics';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * Secondary sign-in: a single shared admin password grants a full-access
 * session. Mirrors the magic-link verify route's response shape
 * (`{ ok, redirectTo }`) so the client redirects the same way.
 */
export async function POST(request: Request) {
  let body: { password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Requête invalide' }, { status: 400 });
  }

  const password = body.password ?? '';
  if (!password) {
    return NextResponse.json({ error: 'Mot de passe requis.' }, { status: 400 });
  }

  const payload = verifyPassword(password);
  if (!payload) {
    return NextResponse.json({ error: 'Mot de passe incorrect.' }, { status: 401 });
  }

  const token = await createSessionToken(payload);
  await setSessionCookie(token);
  await logLogin(payload);
  // Land on the default perimeter (resolved by the home route), not /admin.
  return NextResponse.json({ ok: true, redirectTo: '/' });
}
