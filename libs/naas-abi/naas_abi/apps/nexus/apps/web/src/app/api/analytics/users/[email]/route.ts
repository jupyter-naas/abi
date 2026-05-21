import { NextResponse } from 'next/server';
import { applyFilters, computeUserDetail } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import { getMockEvents } from '@/app/analytics/lib/mock-data';

export const dynamic = 'force-dynamic';

export function GET(req: Request, { params }: { params: { email: string } }) {
  const email = decodeURIComponent(params.email);
  const filters = parseFilters(new URL(req.url));
  const events = applyFilters(getMockEvents(), filters);
  const detail = computeUserDetail(events, email);
  if (!detail) {
    return NextResponse.json({ error: 'No data for user in selected range' }, { status: 404 });
  }
  return NextResponse.json(detail);
}
