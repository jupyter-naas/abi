import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { distinctBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminChartOfAccountsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('chart_of_accounts');

  return (
    <AdminLayout displayName={session.displayName} active="chart-of-accounts">
      <AdminSettingsPage
        description="The chart of accounts every entry is posted against, following the French PCG class structure. Volumes are read back from the general ledger, so an account's activity here is the activity the General Ledger page shows — an account with no lines has genuinely never been used."
        kpis={[
          { label: 'Accounts', value: records.length },
          { label: 'Classes', value: distinctBy(records, 'account_class') },
          { label: 'Posted lines', value: sumBy(records, 'lines') },
          {
            label: 'Total debit',
            value: sumBy(records, 'debit'),
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
            subtitle: 'All periods',
          },
        ]}
        columns={[
          { key: 'account', label: 'Account' },
          { key: 'label', label: 'Label' },
          { key: 'account_class', label: 'Class' },
          { key: 'account_type', label: 'Type' },
          { key: 'journals', label: 'Journals' },
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
          {
            key: 'balance',
            label: 'Balance',
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
        emptyMessage="No account configured."
        exportFileName="chart-of-accounts"
        defaultPageSize={50}
      />
    </AdminLayout>
  );
}
