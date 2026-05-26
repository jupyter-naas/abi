import { NextResponse } from 'next/server';
import { applyFilters, computeWorkspaceRows } from '@/app/analytics/lib/aggregate';
import { parseFilters } from '@/app/analytics/lib/filters';
import { getMockEvents, MOCK_WORKSPACES } from '@/app/analytics/lib/mock-data';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const filters = parseFilters(new URL(req.url));
  const events = applyFilters(getMockEvents(), filters);
  return NextResponse.json({
    workspaces: computeWorkspaceRows(events),
    directory: MOCK_WORKSPACES.map((w) => ({ workspace_id: w.id, workspace_name: w.name })),
  });
}
