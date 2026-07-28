import 'server-only';

import { readFile, stat } from 'fs/promises';
import { join } from 'path';

import { parseSemicolonCsv } from '@/lib/data/csv';
import {
  ALL_ENTITIES_CONSOLIDATION,
  getBusinessControllingRoot,
} from '@/lib/data/businessControllingRoot';
import type {
  ReferentialCategory,
  ReferentialCustomer,
  ReferentialSupplier,
  ReferentialsPayload,
} from '@/lib/pnl/referentials';

const REFERENTIAL_FILES = {
  customers: `consolidations/${ALL_ENTITIES_CONSOLIDATION}/customers/customers.csv`,
  suppliers: `consolidations/${ALL_ENTITIES_CONSOLIDATION}/suppliers/suppliers.csv`,
  categories: `consolidations/${ALL_ENTITIES_CONSOLIDATION}/categories/categories.csv`,
} as const;

type CacheEntry = {
  mtimeMs: number;
  payload: ReferentialsPayload;
};

let cache: CacheEntry | null = null;

async function readReferentialCsv(relativePath: string): Promise<Record<string, string>[]> {
  const fullPath = join(getBusinessControllingRoot(), relativePath);
  try {
    const content = await readFile(fullPath, 'utf8');
    return parseSemicolonCsv(content);
  } catch {
    return [];
  }
}

function mapCustomer(row: Record<string, string>): ReferentialCustomer {
  return {
    organization_slug: row.organization_slug ?? '',
    company_name: row.company_name ?? '',
    customer_name: row.customer_name ?? '',
    customer_vat_number: row.customer_vat_number ?? '',
    customer_billing_address_city: row.customer_billing_address_city ?? '',
    customer_emails: row.customer_emails ?? '',
  };
}

function mapSupplier(row: Record<string, string>): ReferentialSupplier {
  return {
    organization_slug: row.organization_slug ?? '',
    company_name: row.company_name ?? '',
    supplier_name: row.supplier_name ?? '',
    supplier_vat_number: row.supplier_vat_number ?? '',
    supplier_postal_address_city: row.supplier_postal_address_city ?? '',
  };
}

function mapCategory(row: Record<string, string>): ReferentialCategory {
  return {
    organization_slug: row.organization_slug ?? '',
    company_name: row.company_name ?? '',
    category_group_label: row.category_group_label ?? '',
    category_label: row.category_label ?? '',
  };
}

async function loadReferentialsPayload(): Promise<ReferentialsPayload> {
  const paths = Object.values(REFERENTIAL_FILES);
  const mtimes = await Promise.all(
    paths.map(async (relativePath) => {
      try {
        const fileStat = await stat(join(getBusinessControllingRoot(), relativePath));
        return fileStat.mtimeMs;
      } catch {
        return 0;
      }
    }),
  );
  const maxMtime = Math.max(...mtimes);

  if (cache && cache.mtimeMs === maxMtime) {
    return cache.payload;
  }

  const [customerRows, supplierRows, categoryRows] = await Promise.all([
    readReferentialCsv(REFERENTIAL_FILES.customers),
    readReferentialCsv(REFERENTIAL_FILES.suppliers),
    readReferentialCsv(REFERENTIAL_FILES.categories),
  ]);

  const payload: ReferentialsPayload = {
    customers: customerRows.map(mapCustomer),
    suppliers: supplierRows.map(mapSupplier),
    categories: categoryRows.map(mapCategory),
  };

  cache = { mtimeMs: maxMtime, payload };
  return payload;
}

export async function listReferentials(
  organizationSlugs?: ReadonlySet<string>,
): Promise<ReferentialsPayload> {
  const payload = await loadReferentialsPayload();
  if (!organizationSlugs || organizationSlugs.size === 0) {
    return payload;
  }

  const matches = (slug: string) => organizationSlugs.has(slug);
  return {
    customers: payload.customers.filter((row) => matches(row.organization_slug)),
    suppliers: payload.suppliers.filter((row) => matches(row.organization_slug)),
    categories: payload.categories.filter((row) => matches(row.organization_slug)),
  };
}
