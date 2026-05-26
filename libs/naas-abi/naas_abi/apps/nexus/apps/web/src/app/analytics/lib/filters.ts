import type { AnalyticsFilters } from './types';

export function parseFilters(url: URL): AnalyticsFilters {
  const p = url.searchParams;
  const out: AnalyticsFilters = {};
  const start = p.get('start_date');
  const end = p.get('end_date');
  const email = p.get('user_email');
  const ws = p.get('workspace_id');
  if (start) out.start_date = start;
  if (end) out.end_date = end;
  if (email && email !== 'all') out.user_email = email;
  if (ws && ws !== 'all') out.workspace_id = ws;
  return out;
}
