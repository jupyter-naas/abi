'use client';

import { useMemo } from 'react';

import { DataTable, type DataTableColumn } from '@/components/dashboard/DataTable';
import { PageTitle } from '@/components/layout/PageTitle';
import { formatEntityName } from '@/lib/format';
import { useReferentials } from '@/lib/pnl/useReferentials';
import type { SectionProps } from '@/lib/types';

export type ReferentialKind = 'customers' | 'suppliers' | 'categories';

type ReferentialTableSectionProps = SectionProps & {
  kind: ReferentialKind;
  title: string;
  hint: string;
};

const CUSTOMER_COLUMNS: DataTableColumn[] = [
  { key: 'organization_slug', label: 'Organization' },
  { key: 'company_name', label: 'Company' },
  { key: 'customer_name', label: 'Customer' },
  { key: 'customer_vat_number', label: 'VAT' },
  { key: 'customer_billing_address_city', label: 'City' },
  { key: 'customer_emails', label: 'Emails' },
];

const SUPPLIER_COLUMNS: DataTableColumn[] = [
  { key: 'organization_slug', label: 'Organization' },
  { key: 'company_name', label: 'Company' },
  { key: 'supplier_name', label: 'Supplier' },
  { key: 'supplier_vat_number', label: 'VAT' },
  { key: 'supplier_postal_address_city', label: 'City' },
];

const CATEGORY_COLUMNS: DataTableColumn[] = [
  { key: 'organization_slug', label: 'Organization' },
  { key: 'company_name', label: 'Company' },
  { key: 'category_group_label', label: 'Famille_2' },
  { key: 'category_label', label: 'Categorie_2' },
];

export function ReferentialTableSection({
  kind,
  title,
  hint,
  entity,
  company,
  site,
}: ReferentialTableSectionProps) {
  const companySlug = company?.organization_slug ?? null;
  const { payload, loading, error } = useReferentials({
    entitySlug: entity.url_slug,
    companySlug,
  });

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const columns =
    kind === 'customers'
      ? CUSTOMER_COLUMNS
      : kind === 'suppliers'
        ? SUPPLIER_COLUMNS
        : CATEGORY_COLUMNS;

  const records = useMemo(() => {
    if (!payload) {
      return [];
    }
    if (kind === 'customers') {
      return payload.customers as unknown as Record<string, unknown>[];
    }
    if (kind === 'suppliers') {
      return payload.suppliers as unknown as Record<string, unknown>[];
    }
    return payload.categories as unknown as Record<string, unknown>[];
  }, [payload, kind]);

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={hint}>
          {title}
          {perimeterSuffix}
        </PageTitle>
      </div>

      {error ? <p className="mb-4 text-sm text-red-500">{error}</p> : null}

      {loading ? (
        <p className="text-sm text-[var(--text-muted)]">Chargement…</p>
      ) : (
        <DataTable
          records={records}
          columns={columns}
          paginate
          defaultPageSize={20}
          exportable
          exportFileName={`referentiel-${kind}`}
          globalSearch
          globalSearchPlaceholder="Rechercher dans le référentiel…"
          emptyMessage="Aucune entrée dans le référentiel pour ce périmètre."
        />
      )}
    </div>
  );
}
