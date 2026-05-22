import { NextResponse } from 'next/server';
import { applyFilters } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import eventData from '@/app/analytics/data/events.json';
import type { AnalyticsEvent } from '@/app/analytics/lib/types';

export const dynamic = 'force-dynamic';

const ALL_EVENTS = eventData.events as AnalyticsEvent[];

export function GET(req: Request) {
  const url = new URL(req.url);
  const filters = parseFilters(url);
  const limit = Math.max(1, Math.min(1000, Number(url.searchParams.get('limit') ?? '200')));
  const events = applyFilters(ALL_EVENTS, filters).slice(-limit).reverse();
  return NextResponse.json({ events });
}

export function POST(req: Request) {
  // Stub ingestion endpoint — accepts and acknowledges; persistence belongs
  // to a real analytics pipeline.
  return new Promise<Response>((resolve) => {
    req
      .json()
      .then((payload) => resolve(NextResponse.json({ ok: true, received: payload })))
      .catch(() => resolve(NextResponse.json({ ok: false }, { status: 400 })));
  });
}
