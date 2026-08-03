import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminCostCentersPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('cost_centers');
  const fiscalYear = String(records[0]?.fiscal_year ?? '');

  return (
    <AdminLayout displayName={session.displayName} active="cost-centers">
      <AdminSettingsPage
        description="The cost-center referential — the analytical axis every expense line is coded against. This screen configures the roster (code, owner, business unit); the Cost Centers page under Planning is where their performance is analysed."
        kpis={[
          { label: 'Cost centers', value: records.length },
          { label: 'Headcount', value: sumBy(records, 'headcount') },
          {
            label: `Budget ${fiscalYear}`,
            value: sumBy(records, 'annual_budget'),
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
          {
            label: `Actual ${fiscalYear}`,
            value: sumBy(records, 'annual_actual'),
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
        ]}
        columns={[
          { key: 'code', label: 'Code' },
          { key: 'label', label: 'Cost center' },
          { key: 'business_unit', label: 'Business unit' },
          { key: 'owner', label: 'Owner' },
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
        emptyMessage="No cost center configured."
        exportFileName="cost-centers-referential"
      />
    </AdminLayout>
  );
}
