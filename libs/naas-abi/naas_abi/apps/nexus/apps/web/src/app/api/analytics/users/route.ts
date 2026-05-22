import { passthrough } from '@/app/analytics/lib/api-client';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  return passthrough('/users', req.url);
}
