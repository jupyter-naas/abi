import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, distinctBy, readAdminSettings } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminPermissionsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('permissions');

  return (
    <AdminLayout displayName={session.displayName} active="permissions">
      <AdminSettingsPage
        description="The permission matrix: one row per capability, one column per role, so what a role can actually do is readable in a single pass. Permissions are granted through roles only — they are never attached to a user directly."
        kpis={[
          { label: 'Permissions', value: records.length },
          { label: 'Categories', value: distinctBy(records, 'category') },
          {
            label: 'Administration',
            value: countBy(records, 'category', ['Administration']),
            subtitle: 'Reserved to full-access roles',
          },
          {
            label: 'Accounting',
            value: countBy(records, 'category', ['Accounting']),
            subtitle: 'Ledger and close actions',
          },
        ]}
        columns={[
          { key: 'label', label: 'Permission' },
          { key: 'permission', label: 'Key' },
          { key: 'category', label: 'Category' },
          { key: 'owner', label: 'Owner', align: 'right' },
          { key: 'admin', label: 'Admin', align: 'right' },
          { key: 'finance_manager', label: 'Finance Mgr', align: 'right' },
          { key: 'controller', label: 'Controller', align: 'right' },
          { key: 'accountant', label: 'Accountant', align: 'right' },
          { key: 'analyst', label: 'Analyst', align: 'right' },
          { key: 'viewer', label: 'Viewer', align: 'right' },
          { key: 'auditor', label: 'Auditor', align: 'right' },
          { key: 'roles', label: 'Roles', align: 'right' },
          { key: 'description', label: 'Description' },
        ]}
        records={records}
        emptyMessage="No permission configured."
        exportFileName="permissions"
      />
    </AdminLayout>
  );
}
