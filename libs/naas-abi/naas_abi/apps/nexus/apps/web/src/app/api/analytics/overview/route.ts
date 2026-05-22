import { NextResponse } from 'next/server';
import { applyFilters, computeOverview } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import { readEvents } from '@/app/analytics/lib/server-data';

export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const filters = parseFilters(new URL(req.url));
  const all = await readEvents();
  const events = applyFilters(all, filters);
  return NextResponse.json(computeOverview(events, filters));
}
