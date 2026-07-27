import { NextResponse } from 'next/server';

import { getSession } from '@/lib/auth/session';
import { logPageView } from '@/lib/server/analytics';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asNullableString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed || null;
}

/** Best-effort page-view ping from PageViewBeacon.tsx — never errors loudly. */
export async function POST(request: Request) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ ok: true });
  }

  let body: Record<string, unknown> | null;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ ok: true });
  }

  const page = asString(body?.page).trim();
  if (page) {
    await logPageView(session, page, asNullableString(body?.perimeter));
  }
  return NextResponse.json({ ok: true });
}
