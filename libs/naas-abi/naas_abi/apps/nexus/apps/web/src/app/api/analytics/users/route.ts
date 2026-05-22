import { NextResponse } from 'next/server';
import { applyFilters, computeUserRows } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import eventData from '@/app/analytics/data/events.json';
import refUsers from '@/app/analytics/data/ref-users.json';
import type { AnalyticsEvent } from '@/app/analytics/lib/types';

export const dynamic = 'force-dynamic';

const ALL_EVENTS = eventData.events as AnalyticsEvent[];

export function GET(req: Request) {
  const filters = parseFilters(new URL(req.url));
  const events = applyFilters(ALL_EVENTS, filters);
  return NextResponse.json({
    users: computeUserRows(events),
    directory: refUsers,
  });
}
