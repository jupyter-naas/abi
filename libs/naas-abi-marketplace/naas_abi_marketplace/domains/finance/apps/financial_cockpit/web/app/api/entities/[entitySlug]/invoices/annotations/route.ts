import { NextResponse } from 'next/server';
import { notFound } from 'next/navigation';

import { canAccess, getEntity } from '@/lib/config/loadConfig';
import { getSession, isAdminSession } from '@/lib/auth/session';
import {
  deleteInvoiceAnnotationEvents,
  loadInvoiceAnnotations,
  updateInvoiceAnnotationEvent,
  upsertInvoiceAnnotation,
  type AnnotationScope,
} from '@/lib/server/invoiceAnnotations';
import { perimeterSlugsFor } from '@/lib/performance/pnl/perimeter';

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

  if (!canAccess(session, entity.entity_id, 'customer-invoices')) {
    notFound();
  }

  // Events live in one global folder, so every read and write below is limited
  // to the organizations this view covers.
  const scope: AnnotationScope = {
    perimeterSlugs: perimeterSlugsFor(entity, null),
    entityId: entity.entity_id,
  };

  return { entity, session, scope };
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

export async function GET(_request: Request, context: RouteContext) {
  const { scope, error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const { records, history } = await loadInvoiceAnnotations(scope);
  return NextResponse.json({ records, history });
}

export async function PUT(request: Request, context: RouteContext) {
  const { entity, session, scope, error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const payload = await parseJsonBody(request);
  if (!payload) {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const invoiceNumber = asString(payload.invoice_number).trim();
  if (!invoiceNumber) {
    return NextResponse.json({ error: 'invoice_number is required' }, { status: 400 });
  }

  const result = await upsertInvoiceAnnotation(
    entity.entity_id,
    {
      invoice_number: invoiceNumber,
      status_relance: asString(payload.status_relance).trim(),
      date_relance: asString(payload.date_relance).trim(),
      notes: asString(payload.notes),
    },
    {
      company: asString(payload.company),
      organization_slug: asString(payload.organization_slug).trim(),
      site: asString(payload.site),
      client: asString(payload.client),
      categorie_2: asString(payload.categorie_2),
    },
    session.displayName || session.userId,
    scope,
  );
  // Null means organization_slug is outside this view's perimeter.
  if (!result) {
    notFound();
  }

  return NextResponse.json({ record: result.record, log_entries: result.logEntries });
}

export async function PATCH(request: Request, context: RouteContext) {
  const { session, scope, error } = await resolveEntity(context);
  if (error) {
    return error;
  }
  if (!(await isAdminSession(session))) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  const payload = await parseJsonBody(request);
  if (!payload) {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const eventId = asString(payload.event_id).trim();
  if (!eventId) {
    return NextResponse.json({ error: 'event_id is required' }, { status: 400 });
  }

  const updated = await updateInvoiceAnnotationEvent(
    eventId,
    asString(payload.value),
    session.displayName || session.userId,
    scope,
  );
  if (!updated) {
    return NextResponse.json({ error: 'Event not found' }, { status: 404 });
  }

  return NextResponse.json({ record: updated });
}

export async function DELETE(request: Request, context: RouteContext) {
  const { scope, error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const payload = await parseJsonBody(request);
  const eventIds = Array.isArray(payload?.event_ids)
    ? payload.event_ids.filter((id): id is string => typeof id === 'string')
    : [];
  if (eventIds.length === 0) {
    return NextResponse.json({ error: 'event_ids is required' }, { status: 400 });
  }

  const deleted = await deleteInvoiceAnnotationEvents(eventIds, scope);
  return NextResponse.json({ deleted });
}
