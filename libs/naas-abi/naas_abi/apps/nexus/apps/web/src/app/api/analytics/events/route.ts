import { NextResponse } from 'next/server';
import { passthrough } from '@/app/analytics/lib/api-client';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  return passthrough('/events', req.url);
}

export async function POST(req: Request) {
  // Ingestion stub — the analytics service is currently read-only and
  // is fed by the TTL files. Tracking calls are accepted but ignored so
  // the front-end's tracker.ts does not error.
  try {
    const payload = await req.json();
    return NextResponse.json({ ok: true, received: payload });
  } catch {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
}
