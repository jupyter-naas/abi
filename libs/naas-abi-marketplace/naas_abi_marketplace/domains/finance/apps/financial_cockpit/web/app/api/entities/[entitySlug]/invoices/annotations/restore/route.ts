import { NextResponse } from 'next/server';
import { notFound } from 'next/navigation';

import { canAccess, getEntity } from '@/lib/config/loadConfig';
import { getSession, isAdminSession } from '@/lib/auth/session';
import { restoreInvoiceAnnotationEvents } from '@/lib/server/invoiceAnnotations';

export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ entitySlug: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { entitySlug } = await context.params;
  const entity = await getEntity(entitySlug);
  if (!entity) {
    notFound();
  }
  if (!canAccess(session, entity.entity_id, 'customer-invoices')) {
    notFound();
  }
  if (!(await isAdminSession(session))) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  let from: string | undefined;
  try {
    const body = (await request.json()) as { from?: unknown };
    if (typeof body.from === 'string' && body.from.trim()) {
      const parsed = new Date(body.from);
      if (Number.isNaN(parsed.getTime())) {
        return NextResponse.json({ error: 'Invalid from timestamp' }, { status: 400 });
      }
      from = parsed.toISOString();
    }
  } catch {
    // No body → full-history restore.
  }

  const restored = await restoreInvoiceAnnotationEvents(from);
  return NextResponse.json({ restored });
}
