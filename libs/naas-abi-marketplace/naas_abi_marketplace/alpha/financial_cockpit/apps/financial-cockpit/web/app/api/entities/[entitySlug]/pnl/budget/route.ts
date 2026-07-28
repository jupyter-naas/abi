import { NextResponse } from 'next/server';
import { notFound } from 'next/navigation';

import { canAccess, getEntity } from '@/lib/config/loadConfig';
import { getSession } from '@/lib/auth/session';
import {
  deletePnlBudgetRow,
  listPnlBudgetRows,
  upsertPnlBudgetRow,
} from '@/lib/server/pnlStore';
import { validatePnlEntryReferentials } from '@/lib/server/validateReferentialEntry';
import { perimeterSlugsFor } from '@/lib/pnl/perimeter';

export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ entitySlug: string }>;
};

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

  if (!canAccess(session, entity.entity_id, 'pnl-budget')) {
    notFound();
  }

  return { entity, session };
}

async function parseJsonBody(request: Request): Promise<Record<string, unknown> | null> {
  try {
    const body = (await request.json()) as unknown;
    return body && typeof body === 'object' ? (body as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asMonths(value: unknown): number[] {
  const raw = Array.isArray(value) ? value : [];
  return Array.from({ length: 12 }, (_, i) => {
    const n = Number(raw[i]);
    return Number.isFinite(n) ? n : 0;
  });
}

export async function GET(_request: Request, context: RouteContext) {
  const { error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const records = await listPnlBudgetRows();
  return NextResponse.json({ records });
}

export async function PUT(request: Request, context: RouteContext) {
  const { entity, session, error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const payload = await parseJsonBody(request);
  if (!payload) {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const organizationSlug = asString(payload.organization_slug).trim();
  const year = asString(payload.year).trim();
  if (!organizationSlug || !/^\d{4}$/.test(year)) {
    return NextResponse.json(
      { error: 'organization_slug and year (YYYY) are required' },
      { status: 400 },
    );
  }

  const referential = await validatePnlEntryReferentials(
    {
      thirdparty: asString(payload.thirdparty),
      famille_2: asString(payload.famille_2),
      categorie_2: asString(payload.categorie_2),
    },
    perimeterSlugsFor(entity, null),
  );
  if (!referential.ok) {
    return NextResponse.json({ error: referential.errors.join(' · ') }, { status: 400 });
  }

  const record = await upsertPnlBudgetRow(
    asString(payload.id).trim() || null,
    {
      organization_slug: organizationSlug,
      famille_2: referential.normalized.famille_2 ?? asString(payload.famille_2),
      categorie_2: referential.normalized.categorie_2 ?? asString(payload.categorie_2),
      thirdparty: referential.normalized.thirdparty ?? asString(payload.thirdparty),
      year,
      months: asMonths(payload.months),
    },
    session.displayName || session.userId,
  );

  return NextResponse.json({ record });
}

export async function DELETE(request: Request, context: RouteContext) {
  const { error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const payload = await parseJsonBody(request);
  const id = asString(payload?.id).trim();
  if (!id) {
    return NextResponse.json({ error: 'id is required' }, { status: 400 });
  }

  const deleted = await deletePnlBudgetRow(id);
  return NextResponse.json({ deleted });
}
