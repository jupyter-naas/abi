import { NextResponse } from 'next/server';
import { applyFilters, computeUserRows } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import { getMockEvents, MOCK_USERS } from '@/app/analytics/lib/mock-data';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const filters = parseFilters(new URL(req.url));
  const events = applyFilters(getMockEvents(), filters);
  const rows = computeUserRows(events);
  return NextResponse.json({
    users: rows,
    directory: MOCK_USERS.map((u) => ({ user_id: u.id, user_email: u.email })),
  });
}
