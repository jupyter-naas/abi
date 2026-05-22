import { passthrough } from '@/app/analytics/lib/api-client';

export const dynamic = 'force-dynamic';

export function GET(req: Request, { params }: { params: { email: string } }) {
  const email = encodeURIComponent(decodeURIComponent(params.email));
  return passthrough(`/users/${email}`, req.url);
}
