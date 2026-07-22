import { NextResponse } from 'next/server';
import { notFound } from 'next/navigation';

import { canAccess, getEntity } from '@/lib/config/loadConfig';
import { getSession } from '@/lib/auth/session';
import { perimeterSlugsFor } from '@/lib/pnl/perimeter';
import { listReferentials } from '@/lib/server/referentialsStore';
import type { PageId } from '@/lib/types';

export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ entitySlug: string }>;
};

const REFERENTIAL_READ_PAGES: PageId[] = [
  'ref-customers',
  'ref-suppliers',
  'ref-categories',
  'pnl-adjustments',
  'pnl-budget',
];

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

  const allowed = REFERENTIAL_READ_PAGES.some((pageId) =>
    canAccess(session, entity.entity_id, pageId),
  );
  if (!allowed) {
    notFound();
  }

  return { entity, session };
}

export async function GET(request: Request, context: RouteContext) {
  const { entity, error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const url = new URL(request.url);
  const companySlug = url.searchParams.get('company')?.trim() || null;
  const company = companySlug
    ? (entity.companies ?? []).find((entry) => entry.organization_slug === companySlug)
    : null;

  const perimeterSlugs = perimeterSlugsFor(entity, company ?? null);
  const payload = await listReferentials(perimeterSlugs);

  return NextResponse.json(payload);
}
