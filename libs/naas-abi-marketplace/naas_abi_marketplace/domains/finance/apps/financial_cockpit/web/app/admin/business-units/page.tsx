import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminBusinessUnitsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('business_units');
  const fiscalYear = String(records[0]?.fiscal_year ?? '');

  return (
    <AdminLayout displayName={session.displayName} active="business-units">
      <AdminSettingsPage
        description="Business units are the first level of the organization: every cost center belongs to exactly one, and the figures below are the roster's own budget and actuals rolled up. Budget, actual and headcount come from the Cost Centers page, so the two always agree."
        kpis={[
          { label: 'Business units', value: records.length },
          { label: 'Cost centers', value: sumBy(records, 'cost_centers') },
          {
            label: 'Headcount',
            value: sumBy(records, 'headcount'),
            subtitle: 'Latest closed month',
          },
          {
            label: `Budget ${fiscalYear}`,
            value: sumBy(records, 'annual_budget'),
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
        ]}
        columns={[
          { key: 'code', label: 'Code' },
          { key: 'label', label: 'Business unit' },
          { key: 'parent', label: 'Parent entity' },
          { key: 'manager', label: 'Manager' },
          { key: 'cost_centers', label: 'Cost centers', align: 'right' },
          { key: 'headcount', label: 'Headcount', align: 'right' },
          {
            key: 'annual_budget',
            label: 'Annual budget',
            align: 'right',
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
          {
            key: 'annual_actual',
            label: 'Annual actual',
            align: 'right',
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No business unit configured."
        exportFileName="business-units"
      />
    </AdminLayout>
  );
}
