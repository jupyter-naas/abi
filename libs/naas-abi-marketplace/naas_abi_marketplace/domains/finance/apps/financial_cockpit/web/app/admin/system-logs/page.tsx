import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, distinctBy, readAdminSettings } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminSystemLogsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('system_logs');
  const errors = countBy(records, 'level', ['ERROR']);
  const warnings = countBy(records, 'level', ['WARN']);

  return (
    <AdminLayout displayName={session.displayName} active="system-logs">
      <AdminSettingsPage
        description="The technical trail behind the platform — scheduled jobs, dataset publications, authentication and API traffic. User Activity answers who looked at what; this page answers what the system itself did, and is where a failed sync or a rejected sign-in is diagnosed."
        kpis={[
          { label: 'Events', value: records.length },
          {
            label: 'Errors',
            value: errors,
            tone: errors > 0 ? 'danger' : 'default',
          },
          {
            label: 'Warnings',
            value: warnings,
            tone: warnings > 0 ? 'warning' : 'default',
          },
          { label: 'Components', value: distinctBy(records, 'component') },
        ]}
        columns={[
          { key: 'timestamp', label: 'Timestamp' },
          { key: 'level', label: 'Level' },
          { key: 'component', label: 'Component' },
          { key: 'event', label: 'Event' },
          { key: 'message', label: 'Message' },
          { key: 'actor', label: 'Actor' },
          { key: 'duration_ms', label: 'Duration (ms)', align: 'right' },
        ]}
        records={records}
        statusColumns={['level']}
        emptyMessage="No system event logged."
        exportFileName="system-logs"
        defaultPageSize={50}
      />
    </AdminLayout>
  );
}
