import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminSyncHistoryPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('sync_history');
  const failed = countBy(records, 'status', ['Failed']);

  return (
    <AdminLayout displayName={session.displayName} active="sync-history">
      <AdminSettingsPage
        description="Every run of every connector, newest first: what it pulled or pushed, how long it took and whether it landed. A failed run leaves the previous data in place, so this is where to look when a finance page seems to be missing a day."
        kpis={[
          { label: 'Runs', value: records.length },
          {
            label: 'Succeeded',
            value: countBy(records, 'status', ['Succeeded']),
            tone: 'success',
          },
          {
            label: 'Failed',
            value: failed,
            tone: failed > 0 ? 'danger' : 'default',
          },
          { label: 'Records synced', value: sumBy(records, 'records') },
        ]}
        columns={[
          { key: 'started_at', label: 'Started' },
          { key: 'connector', label: 'Connector' },
          { key: 'sync_type', label: 'Type' },
          { key: 'direction', label: 'Direction' },
          { key: 'records', label: 'Records', align: 'right' },
          { key: 'created', label: 'Created', align: 'right' },
          { key: 'updated', label: 'Updated', align: 'right' },
          { key: 'errors', label: 'Errors', align: 'right' },
          {
            key: 'duration_s',
            label: 'Duration (s)',
            align: 'right',
            maximumFractionDigits: 1,
          },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No synchronization run recorded."
        exportFileName="synchronization-history"
        defaultPageSize={50}
      />
    </AdminLayout>
  );
}
