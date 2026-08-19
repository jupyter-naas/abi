import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminApiIntegrationsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('integrations_api');
  const idle = countBy(records, 'status', ['Idle']);

  return (
    <AdminLayout displayName={session.displayName} active="integrations-api">
      <AdminSettingsPage
        description="API clients allowed to read the datastore or write back to it. Keys are shown by prefix only — the secret is displayed once at creation and never again. An idle key has made no call in the last 30 days and is the first thing to revoke."
        kpis={[
          { label: 'API clients', value: records.length },
          {
            label: 'Active',
            value: countBy(records, 'status', ['Active']),
            tone: 'success',
          },
          {
            label: 'Idle keys',
            value: idle,
            tone: idle > 0 ? 'warning' : 'default',
            subtitle: 'No call in 30 days',
          },
          {
            label: 'Calls',
            value: sumBy(records, 'calls_30d'),
            subtitle: 'Last 30 days',
          },
        ]}
        columns={[
          { key: 'client', label: 'Client' },
          { key: 'key_prefix', label: 'Key' },
          { key: 'scopes', label: 'Scopes' },
          { key: 'environment', label: 'Environment' },
          { key: 'rate_limit_per_min', label: 'Rate limit / min', align: 'right' },
          { key: 'created_on', label: 'Created' },
          { key: 'last_used', label: 'Last used' },
          { key: 'calls_30d', label: 'Calls (30 d)', align: 'right' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No API client configured."
        exportFileName="integrations-api"
      />
    </AdminLayout>
  );
}
