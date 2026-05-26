import { NextResponse } from 'next/server';
import { applyFilters, computeOverview } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import { getMockEvents } from '@/app/analytics/lib/mock-data';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const filters = parseFilters(new URL(req.url));
  const events = applyFilters(getMockEvents(), filters);
  return NextResponse.json(computeOverview(events, filters));
}
