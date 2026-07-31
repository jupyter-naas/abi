import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminAccountingPeriodsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('accounting_periods');
  const open = countBy(records, 'status', ['Open']);

  return (
    <AdminLayout displayName={session.displayName} active="accounting-periods">
      <AdminSettingsPage
        description="Monthly periods and their lock state. A closed period rejects any new posting — the &ldquo;Closed period is locked&rdquo; validation rule enforces it — and is reopened only by an administrator. The status shown here is the same one the Financial Close page works towards."
        kpis={[
          { label: 'Periods', value: records.length },
          { label: 'Closed', value: countBy(records, 'status', ['Closed']) },
          {
            label: 'Open',
            value: open,
            tone: open > 0 ? 'warning' : 'default',
          },
          {
            label: 'Manual entries',
            value: sumBy(records, 'manual_entries'),
            subtitle: 'All periods',
          },
        ]}
        columns={[
          { key: 'period', label: 'Period' },
          { key: 'label', label: 'Label' },
          { key: 'fiscal_year', label: 'Fiscal year' },
          { key: 'start_date', label: 'Start' },
          { key: 'end_date', label: 'End' },
          { key: 'entries', label: 'Entries', align: 'right' },
          { key: 'lines', label: 'Lines', align: 'right' },
          { key: 'manual_entries', label: 'Manual', align: 'right' },
          {
            key: 'debit',
            label: 'Total debit',
            align: 'right',
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
          { key: 'locked_on', label: 'Locked on' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No accounting period configured."
        exportFileName="accounting-periods"
        defaultPageSize={50}
      />
    </AdminLayout>
  );
}
