import { proxyAnalytics } from '../_proxy';

export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  return proxyAnalytics('workspaces', req);
}
