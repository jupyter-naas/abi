import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, distinctBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminBankingIntegrationsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('integrations_banking');
  const stale = countBy(records, 'status', ['Stale']);

  return (
    <AdminLayout displayName={session.displayName} active="integrations-banking">
      <AdminSettingsPage
        description="Bank feeds behind the Cash Position and Cash Forecast pages — one connector per bank and currency. A stale feed means the last statement is older than its schedule allows, so the balances shown on those pages are behind reality until it catches up."
        kpis={[
          { label: 'Feeds', value: records.length },
          { label: 'Banks', value: distinctBy(records, 'bank') },
          { label: 'Bank accounts', value: sumBy(records, 'accounts') },
          {
            label: 'Stale feeds',
            value: stale,
            tone: stale > 0 ? 'warning' : 'default',
            subtitle: 'Behind schedule',
          },
        ]}
        columns={[
          { key: 'connector', label: 'Feed' },
          { key: 'bank', label: 'Bank' },
          { key: 'country', label: 'Country' },
          { key: 'currency', label: 'Currency' },
          { key: 'protocol', label: 'Protocol' },
          { key: 'accounts', label: 'Accounts', align: 'right' },
          { key: 'frequency', label: 'Frequency' },
          { key: 'last_sync', label: 'Last sync' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No bank feed configured."
        exportFileName="integrations-banking"
      />
    </AdminLayout>
  );
}
