import { NextResponse } from 'next/server';
import { notFound } from 'next/navigation';

import { canAccess, getEntity } from '@/lib/config/loadConfig';
import { getSession } from '@/lib/auth/session';
import { listPnlAdjustments } from '@/lib/server/pnlStore';
import { perimeterSlugsFor } from '@/lib/performance/pnl/perimeter';
import type { PageId } from '@/lib/types';

export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ entitySlug: string }>;
};

/** Pages that merge the adjustments into their own figures (read-only). */
const ADJUSTMENT_READ_PAGES: PageId[] = ['pnl', 'pnl-budget'];

async function resolveEntity(context: RouteContext) {
  const session = await getSession();
  if (!session) {
    return { error: NextResponse.json({ error: 'Unauthorized' }, { status: 401 }) };
  }

  const { entitySlug } = await context.params;
  const entity = await getEntity(entitySlug);
  if (!entity) {
    notFound();
  }

  const allowed = ADJUSTMENT_READ_PAGES.some((pageId) =>
    canAccess(session, entity.entity_id, pageId),
  );
  if (!allowed) {
    notFound();
  }

  return { entity, session };
}

export async function GET(_request: Request, context: RouteContext) {
  const { entity, error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const records = await listPnlAdjustments(perimeterSlugsFor(entity, null));
  return NextResponse.json({ records });
}
