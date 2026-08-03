import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminValidationRulesPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('validation_rules');

  return (
    <AdminLayout displayName={session.displayName} active="validation-rules">
      <AdminSettingsPage
        description="The controls applied before a document is accepted. A blocking rule rejects the posting outright; a warning lets it through but flags it to the preparer and, where relevant, raises a close task. The trigger count is the last 30 days."
        kpis={[
          { label: 'Rules', value: records.length },
          {
            label: 'Blocking',
            value: countBy(records, 'severity', ['Blocking']),
            subtitle: 'Reject the posting',
          },
          {
            label: 'Warnings',
            value: countBy(records, 'severity', ['Warning']),
          },
          {
            label: 'Triggered',
            value: sumBy(records, 'triggered_30d'),
            subtitle: 'Last 30 days',
          },
        ]}
        columns={[
          { key: 'rule', label: 'Rule' },
          { key: 'scope', label: 'Scope' },
          { key: 'severity', label: 'Severity' },
          { key: 'condition', label: 'Condition' },
          { key: 'action', label: 'Action' },
          { key: 'triggered_30d', label: 'Triggered (30 d)', align: 'right' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['severity', 'status']}
        emptyMessage="No validation rule configured."
        exportFileName="validation-rules"
      />
    </AdminLayout>
  );
}
