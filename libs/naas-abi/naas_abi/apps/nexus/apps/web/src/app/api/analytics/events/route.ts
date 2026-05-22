import { NextResponse } from 'next/server';
import { applyFilters } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import { readEvents } from '@/app/analytics/lib/server-data';

export const dynamic = 'force-dynamic';

// Ingestion has moved to the Nexus API: POST /api/analytics/events on port
// 9879. That endpoint writes through ABI's object storage service and
// mirrors to the local data dir, which this GET reads.
export async function GET(req: Request) {
  const url = new URL(req.url);
  const filters = parseFilters(url);
  const limit = Math.max(1, Math.min(1000, Number(url.searchParams.get('limit') ?? '200')));
  const all = await readEvents();
  const events = applyFilters(all, filters).slice(-limit).reverse();
  return NextResponse.json({ events });
}
