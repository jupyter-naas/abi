import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminErpIntegrationsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('integrations_erp');
  const errors = countBy(records, 'status', ['Error']);

  return (
    <AdminLayout displayName={session.displayName} active="integrations-erp">
      <AdminSettingsPage
        description="Connectors to the accounting and payroll systems that feed the cockpit. Inbound connectors write into the datastore the finance pages read; the outbound one republishes it downstream. A connector in error keeps serving its last successful sync — the data goes stale rather than empty."
        kpis={[
          { label: 'Connectors', value: records.length },
          {
            label: 'Connected',
            value: countBy(records, 'status', ['Connected']),
            tone: 'success',
          },
          {
            label: 'In error',
            value: errors,
            tone: errors > 0 ? 'danger' : 'default',
          },
          {
            label: 'Records',
            value: sumBy(records, 'records_30d'),
            subtitle: 'Last 30 days',
          },
        ]}
        columns={[
          { key: 'connector', label: 'Connector' },
          { key: 'system', label: 'System' },
          { key: 'environment', label: 'Environment' },
          { key: 'scope', label: 'Scope' },
          { key: 'direction', label: 'Direction' },
          { key: 'frequency', label: 'Frequency' },
          { key: 'last_sync', label: 'Last sync' },
          { key: 'records_30d', label: 'Records (30 d)', align: 'right' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No ERP connector configured."
        exportFileName="integrations-erp"
      />
    </AdminLayout>
  );
}
