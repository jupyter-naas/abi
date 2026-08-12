import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, readAdminSettings, sumBy } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminRolesPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('roles');

  return (
    <AdminLayout displayName={session.displayName} active="roles">
      <AdminSettingsPage
        description="A role is a named bundle of permissions plus the scope it applies to — global (every perimeter) or perimeter-bound. Owner is the protected root identity declared in config.yaml and can never be edited from the app; every other role is managed here and assigned on the Users screen."
        kpis={[
          { label: 'Roles', value: records.length },
          {
            label: 'Global scope',
            value: countBy(records, 'scope', ['Global']),
            subtitle: 'Access to every perimeter',
          },
          { label: 'Users assigned', value: sumBy(records, 'users') },
          {
            label: 'Protected',
            value: countBy(records, 'status', ['Protected']),
            subtitle: 'Not editable from the app',
          },
        ]}
        columns={[
          { key: 'role', label: 'Role' },
          { key: 'key', label: 'Key' },
          { key: 'scope', label: 'Scope' },
          { key: 'permissions', label: 'Permissions', align: 'right' },
          { key: 'users', label: 'Users', align: 'right' },
          { key: 'managed_in', label: 'Managed in' },
          { key: 'status', label: 'Status' },
          { key: 'description', label: 'Description' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No role configured."
        exportFileName="roles"
      />
    </AdminLayout>
  );
}
