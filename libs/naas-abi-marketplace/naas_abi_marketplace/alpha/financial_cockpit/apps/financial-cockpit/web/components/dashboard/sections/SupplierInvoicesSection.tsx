'use client';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { PageTitle } from '@/components/layout/PageTitle';

/**
 * Placeholder — mirrors "Impayés Clients" (unpaid customer invoices) but for supplier
 * invoices. No supplier-invoice seed pipeline exists yet in business_controlling
 * (treasury reads suppliers_invoices.csv only for cash projection, not for a
 * standalone aging/follow-up dashboard); wire this up once that data lands.
 */
export function SupplierInvoicesSection({ company, site }: SectionProps) {
  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint="Suivi des factures fournisseurs (à venir).">
          Dettes Fournisseurs{perimeterSuffix}
        </PageTitle>
      </div>
      <div className="glass rounded-lg p-6">
        <p className="text-sm text-[var(--text-muted)]">
          Le suivi des factures fournisseurs n&apos;est pas encore disponible pour ce
          périmètre.
        </p>
      </div>
    </div>
  );
}
