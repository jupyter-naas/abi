import { NextResponse } from 'next/server';
import { notFound } from 'next/navigation';

import { canAccess, getEntity } from '@/lib/config/loadConfig';
import { getSession, isAdminSession } from '@/lib/auth/session';
import {
  deleteInvoiceAnnotationEvents,
  loadInvoiceAnnotations,
  updateInvoiceAnnotationEvent,
  upsertInvoiceAnnotation,
} from '@/lib/server/invoiceAnnotations';

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

export async function GET(_request: Request, context: RouteContext) {
  const { error } = await resolveEntity(context);
  if (error) {
    return error;
  }

  const { records, history } = await loadInvoiceAnnotations();
  return NextResponse.json({ records, history });
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

  const invoiceNumber = asString(payload.invoice_number).trim();
  if (!invoiceNumber) {
    return NextResponse.json({ error: 'invoice_number is required' }, { status: 400 });
  }

  const { record, logEntries } = await upsertInvoiceAnnotation(
    entity.entity_id,
    {
      invoice_number: invoiceNumber,
      status_relance: asString(payload.status_relance).trim(),
      date_relance: asString(payload.date_relance).trim(),
      notes: asString(payload.notes),
    },
    {
      company: asString(payload.company),
      organization_slug: asString(payload.organization_slug),
      site: asString(payload.site),
      client: asString(payload.client),
      categorie_2: asString(payload.categorie_2),
    },
    session.displayName || session.userId,
  );

  return NextResponse.json({ record, log_entries: logEntries });
}

export async function PATCH(request: Request, context: RouteContext) {
  const { session, error } = await resolveEntity(context);
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
  );
  if (!updated) {
    return NextResponse.json({ error: 'Event not found' }, { status: 404 });
  }

  return NextResponse.json({ record: updated });
}

export async function DELETE(request: Request, context: RouteContext) {
  const { error } = await resolveEntity(context);
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

  const deleted = await deleteInvoiceAnnotationEvents(eventIds);
  return NextResponse.json({ deleted });
}
