import { NextResponse } from 'next/server';
import { notFound } from 'next/navigation';

import { canAccess, getEntity } from '@/lib/config/loadConfig';
import { getSession } from '@/lib/auth/session';
import { readCachedInvoicePdf } from '@/lib/server/invoicePdf';

export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ entitySlug: string; invoiceId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { entitySlug, invoiceId } = await context.params;
  const entity = await getEntity(entitySlug);
  if (!entity) {
    notFound();
  }

  if (!canAccess(session, entity.entity_id, 'customer-invoices')) {
    notFound();
  }

  const url = new URL(request.url);
  const organizationSlug = url.searchParams.get('organizationSlug')?.trim();
  if (!organizationSlug) {
    return NextResponse.json({ error: 'organizationSlug is required' }, { status: 400 });
  }

  const disposition = url.searchParams.get('disposition') === 'attachment' ? 'attachment' : 'inline';
  const invoiceRef = url.searchParams.get('invoiceRef')?.trim() || invoiceId;
  const safeFileName = invoiceRef.replace(/[^\w.-]+/g, '_');
  const invoiceType = url.searchParams.get('type') === 'supplier' ? 'supplier' : 'customer';

  const pdf = await readCachedInvoicePdf(organizationSlug, invoiceId, invoiceType);
  if (!pdf) {
    return NextResponse.json(
      { error: 'Invoice PDF not found. Run make fin-organizations-database then make fin-app-invoices.' },
      { status: 404 },
    );
  }

  return new NextResponse(new Uint8Array(pdf), {
    status: 200,
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': `${disposition}; filename="${safeFileName}.pdf"`,
      'Cache-Control': 'private, max-age=3600',
    },
  });
}
