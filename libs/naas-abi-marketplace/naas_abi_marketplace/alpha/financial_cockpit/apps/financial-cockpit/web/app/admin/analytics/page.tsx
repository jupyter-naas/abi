import { notFound } from 'next/navigation';

import { AnalyticsDashboard } from '@/components/admin/AnalyticsDashboard';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { getEntities } from '@/lib/config/loadConfig';
import { getAllUsers } from '@/lib/server/financeUsers';
import { loadAnalyticsEvents } from '@/lib/server/analytics';

export const dynamic = 'force-dynamic';

export default async function AdminAnalyticsPage() {
  const session = await requireAdmin().catch(() => notFound());

  const [events, entities, users] = await Promise.all([
    loadAnalyticsEvents(),
    getEntities(),
    getAllUsers(),
  ]);

  const emailByUserId = new Map(users.map((u) => [u.user_id, u.email]));
  const enrichedEvents = events.map((e) => ({
    ...e,
    email: emailByUserId.get(e.user_id) ?? null,
  }));

  return (
    <AdminLayout displayName={session.displayName} active="analytics">
      <AnalyticsDashboard events={enrichedEvents} entities={entities} />
    </AdminLayout>
  );
}
