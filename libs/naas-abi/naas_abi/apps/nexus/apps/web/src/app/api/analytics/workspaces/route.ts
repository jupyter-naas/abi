import { NextResponse } from 'next/server';
import { applyFilters, computeWorkspaceRows } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import eventData from '@/app/analytics/data/events.json';
import refWorkspaces from '@/app/analytics/data/ref-workspaces.json';
import type { AnalyticsEvent } from '@/app/analytics/lib/types';

export const dynamic = 'force-dynamic';

const ALL_EVENTS = eventData.events as AnalyticsEvent[];

export function GET(req: Request) {
  const filters = parseFilters(new URL(req.url));
  const events = applyFilters(ALL_EVENTS, filters);
  return NextResponse.json({
    workspaces: computeWorkspaceRows(events),
    directory: refWorkspaces,
  });
}
