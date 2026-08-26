import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminApprovalFlowsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('approval_flows');
  const active = countBy(records, 'status', ['Active']);
  const avgSla = records.length > 0 ? sumBy(records, 'sla_days') / records.length : 0;

  return (
    <AdminLayout displayName={session.displayName} active="approval-flows">
      <AdminSettingsPage
        description="Who has to approve what, and above which amount. A flow fires on its trigger, routes through its steps in order, and escalates when the SLA expires. Thresholds are read as “from this amount up”, so a document can match several flows and takes the strictest."
        kpis={[
          { label: 'Approval flows', value: records.length },
          { label: 'Active', value: active, tone: 'success' },
          { label: 'Approval steps', value: sumBy(records, 'steps') },
          {
            label: 'Average SLA',
            value: avgSla,
            maximumFractionDigits: 1,
            subtitle: 'Business days per step',
          },
        ]}
        columns={[
          { key: 'flow', label: 'Flow' },
          { key: 'object', label: 'Object' },
          { key: 'trigger', label: 'Trigger' },
          {
            key: 'threshold',
            label: 'Threshold',
            align: 'right',
            valueStyle: 'currency',
            currency: 'EUR',
            maximumFractionDigits: 0,
          },
          { key: 'steps', label: 'Steps', align: 'right' },
          { key: 'approvers', label: 'Approvers' },
          { key: 'sla_days', label: 'SLA (days)', align: 'right' },
          { key: 'auto_escalation', label: 'Auto-escalation' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No approval flow configured."
        exportFileName="approval-flows"
      />
    </AdminLayout>
  );
}
