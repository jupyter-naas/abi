import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminFiscalYearsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('fiscal_years');
  const open = countBy(records, 'status', ['Open']);

  return (
    <AdminLayout displayName={session.displayName} active="fiscal-years">
      <AdminSettingsPage
        description="Fiscal years bound what can still be posted. A year is closed once all twelve of its periods are locked; until then it stays open and entries can still reach it. The demo instance runs on calendar years."
        kpis={[
          { label: 'Fiscal years', value: records.length },
          { label: 'Closed', value: countBy(records, 'status', ['Closed']) },
          {
            label: 'Open',
            value: open,
            tone: open > 0 ? 'warning' : 'default',
            subtitle: 'Still accepting entries',
          },
          { label: 'Entries', value: sumBy(records, 'entries') },
        ]}
        columns={[
          { key: 'fiscal_year', label: 'Fiscal year' },
          { key: 'start_date', label: 'Start' },
          { key: 'end_date', label: 'End' },
          { key: 'periods', label: 'Periods', align: 'right' },
          { key: 'closed_periods', label: 'Closed periods', align: 'right' },
          { key: 'entries', label: 'Entries', align: 'right' },
          { key: 'lines', label: 'Lines', align: 'right' },
          {
            key: 'debit',
            label: 'Total debit',
            align: 'right',
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
          { key: 'closed_on', label: 'Closed on' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No fiscal year configured."
        exportFileName="fiscal-years"
      />
    </AdminLayout>
  );
}
