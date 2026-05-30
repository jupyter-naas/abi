import { proxyAnalytics } from '../../_proxy';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: { id: string } }) {
  return proxyAnalytics(`chats/${encodeURIComponent(params.id)}`, req);
}
