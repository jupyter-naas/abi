import 'server-only';

import { toR2ObjectKey } from '@/lib/server/dataKeys';
import { existsSync } from 'fs';
import { readFile } from 'fs/promises';
import { join } from 'path';

const DEFAULT_DATASTORE_ROOT = join(
  '..',
  '..',
  '..',
  '..',
  '..',
  'storage',
  'datastore',
  'business_controlling',
  'apps',
  'finance',
  'data',
);

function isProd(): boolean {
  return process.env.ENV === 'prod';
}

function getDatastoreRoot(): string {
  return process.env.DATA_LOCAL_ROOT ?? DEFAULT_DATASTORE_ROOT;
}

export type InvoicePdfType = 'customer' | 'supplier';

export function invoicePdfRelativeKey(
  organizationSlug: string,
  invoiceId: string,
  invoiceType: InvoicePdfType = 'customer',
): string {
  const dir = invoiceType === 'supplier' ? 'supplier_invoices' : 'customer_invoices';
  return `entities/${organizationSlug}/${dir}/pdf/${invoiceId}.pdf`;
}

function resolveLocalPdfPath(relativeKey: string): string | null {
  const datastorePath = join(process.cwd(), getDatastoreRoot(), relativeKey);
  if (existsSync(datastorePath)) {
    return datastorePath;
  }
  return null;
}

export function invoicePdfCachePath(
  organizationSlug: string,
  invoiceId: string,
  invoiceType: InvoicePdfType = 'customer',
): string {
  return join(
    process.cwd(),
    getDatastoreRoot(),
    invoicePdfRelativeKey(organizationSlug, invoiceId, invoiceType),
  );
}

export function isInvoicePdfCached(
  organizationSlug: string,
  invoiceId: string,
  invoiceType: InvoicePdfType = 'customer',
): boolean {
  return resolveLocalPdfPath(invoicePdfRelativeKey(organizationSlug, invoiceId, invoiceType)) !== null;
}

async function readR2Pdf(relativeKey: string): Promise<Buffer | null> {
  try {
    const { getCloudflareContext } = await import('@opennextjs/cloudflare');
    const ctx = await getCloudflareContext({ async: true });
    const bucket = (ctx.env as { DATASETS?: R2Bucket }).DATASETS;
    if (!bucket) {
      return null;
    }
    const object = await bucket.get(toR2ObjectKey(relativeKey));
    if (!object) {
      return null;
    }
    return Buffer.from(await object.arrayBuffer());
  } catch {
    return null;
  }
}

export async function readCachedInvoicePdf(
  organizationSlug: string,
  invoiceId: string,
  invoiceType: InvoicePdfType = 'customer',
): Promise<Buffer | null> {
  const relativeKey = invoicePdfRelativeKey(organizationSlug, invoiceId, invoiceType);

  if (isProd()) {
    return readR2Pdf(relativeKey);
  }

  const path = resolveLocalPdfPath(relativeKey);
  if (!path) {
    return null;
  }
  return readFile(path);
}

interface R2Bucket {
  get(key: string): Promise<{ arrayBuffer(): Promise<ArrayBuffer> } | null>;
}
