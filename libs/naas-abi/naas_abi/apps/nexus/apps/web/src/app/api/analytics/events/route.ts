import { proxyAnalytics } from '../_proxy';

export const dynamic = 'force-dynamic';

// Ingestion has moved to the Nexus API: POST /api/analytics/events on port
// 9879. That endpoint writes through ABI's object storage service.
export async function GET(req: Request) {
  return proxyAnalytics('events', req);
}
