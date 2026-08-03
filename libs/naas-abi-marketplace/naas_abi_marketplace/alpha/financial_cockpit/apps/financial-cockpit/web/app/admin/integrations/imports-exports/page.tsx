import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminImportsExportsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('imports_exports');
  const failed = countBy(records, 'status', ['Failed']);

  return (
    <AdminLayout displayName={session.displayName} active="imports-exports">
      <AdminSettingsPage
        description="File-based exchanges that sit alongside the live connectors: spreadsheet imports for budget and adjustment entries, and the scheduled extracts sent to the warehouse, the auditor and the tax authority. Status is the outcome of the last run."
        kpis={[
          { label: 'Jobs', value: records.length },
          { label: 'Imports', value: countBy(records, 'direction', ['Import']) },
          { label: 'Exports', value: countBy(records, 'direction', ['Export']) },
          {
            label: 'Failed last run',
            value: failed,
            tone: failed > 0 ? 'danger' : 'default',
          },
        ]}
        columns={[
          { key: 'job', label: 'Job' },
          { key: 'direction', label: 'Direction' },
          { key: 'format', label: 'Format' },
          { key: 'target', label: 'Source / target' },
          { key: 'schedule', label: 'Schedule' },
          { key: 'last_run', label: 'Last run' },
          { key: 'rows', label: 'Rows', align: 'right' },
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
        emptyMessage="No import or export job configured."
        exportFileName="imports-exports"
      />
    </AdminLayout>
  );
}
