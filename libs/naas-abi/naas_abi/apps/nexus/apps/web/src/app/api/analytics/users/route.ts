import { NextResponse } from 'next/server';
import { applyFilters, computeUserRows } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import { readEvents, readRefUsers } from '@/app/analytics/lib/server-data';

export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const filters = parseFilters(new URL(req.url));
  const [all, directory] = await Promise.all([readEvents(), readRefUsers()]);
  const events = applyFilters(all, filters);
  return NextResponse.json({
    users: computeUserRows(events),
    directory,
  });
}
