import { proxyAnalytics } from '../../_proxy';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyAnalytics(`chats/${encodeURIComponent(id)}`, req);
}
