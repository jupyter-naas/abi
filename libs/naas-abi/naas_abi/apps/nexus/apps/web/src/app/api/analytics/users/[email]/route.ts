import { proxyAnalytics } from '../../_proxy';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: Promise<{ email: string }> }) {
  const { email } = await params;
  return proxyAnalytics(`users/${encodeURIComponent(email)}`, req);
}
