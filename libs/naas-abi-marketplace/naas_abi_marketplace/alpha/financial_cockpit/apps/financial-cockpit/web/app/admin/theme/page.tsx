import { notFound } from 'next/navigation';

import { ThemeSection } from '@/components/dashboard/sections/ThemeSection';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';

export const dynamic = 'force-dynamic';

export default async function AdminThemePage() {
  const session = await requireAdmin().catch(() => notFound());

  return (
    <AdminLayout displayName={session.displayName} active="theme">
      <ThemeSection />
    </AdminLayout>
  );
}
