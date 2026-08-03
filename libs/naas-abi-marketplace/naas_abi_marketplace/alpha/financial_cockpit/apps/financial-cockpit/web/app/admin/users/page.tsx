import { notFound } from 'next/navigation';

import { UserManager } from '@/components/admin/UserManager';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { getEntities, getPageLabel } from '@/lib/config/loadConfig';
import {
  getAssignablePages,
  listProtectedUsers,
  loadDatastoreUsers,
} from '@/lib/server/financeUsers';

export const dynamic = 'force-dynamic';

export default async function AdminUsersPage() {
  const session = await requireAdmin().catch(() => notFound());

  const [configUsers, datastoreUsers, entities] = await Promise.all([
    Promise.resolve(listProtectedUsers()),
    loadDatastoreUsers(),
    getEntities(),
  ]);

  const pages = getAssignablePages().map((pageId) => ({
    page_id: pageId,
    label: getPageLabel(pageId),
  }));

  return (
    <AdminLayout displayName={session.displayName} active="users">
      <UserManager
        configUsers={configUsers}
        initialUsers={datastoreUsers}
        entities={entities}
        pages={pages}
      />
    </AdminLayout>
  );
}
