import { proxyAnalytics } from '../../_proxy';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: { email: string } }) {
  return proxyAnalytics(`users/${encodeURIComponent(params.email)}`, req);
}
