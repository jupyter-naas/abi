import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminJournalsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('journals');

  return (
    <AdminLayout displayName={session.displayName} active="journals">
      <AdminSettingsPage
        description="Journals classify every posting by origin: sales, purchases, payroll and bank are fed automatically by the connectors, while miscellaneous carries the manual entries that go through validation. Counts are read back from the general ledger."
        kpis={[
          { label: 'Journals', value: records.length },
          {
            label: 'Manual posting',
            value: countBy(records, 'posting', ['Manual']),
            subtitle: 'Requires validation',
          },
          { label: 'Entries', value: sumBy(records, 'entries') },
          { label: 'Lines', value: sumBy(records, 'lines') },
        ]}
        columns={[
          { key: 'journal_code', label: 'Code' },
          { key: 'label', label: 'Journal' },
          { key: 'journal_type', label: 'Type' },
          { key: 'posting', label: 'Posting' },
          { key: 'accounts', label: 'Accounts', align: 'right' },
          { key: 'entries', label: 'Entries', align: 'right' },
          { key: 'lines', label: 'Lines', align: 'right' },
          {
            key: 'debit',
            label: 'Debit',
            align: 'right',
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
          {
            key: 'credit',
            label: 'Credit',
            align: 'right',
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
          { key: 'last_entry', label: 'Last entry' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No journal configured."
        exportFileName="journals"
      />
    </AdminLayout>
  );
}
