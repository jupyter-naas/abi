import { notFound } from 'next/navigation';

import { AdminSettingsPage } from '@/components/admin/AdminSettingsPage';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import { countBy, distinctBy, readAdminSettings } from '@/lib/admin/settings';

export const dynamic = 'force-dynamic';

export default async function AdminNotificationsPage() {
  const session = await requireAdmin().catch(() => notFound());
  const records = await readAdminSettings('notifications');
  const paused = countBy(records, 'status', ['Paused']);

  return (
    <AdminLayout displayName={session.displayName} active="notifications">
      <AdminSettingsPage
        description="Which events reach whom, through which channel and at what cadence. Immediate notifications fire on the event itself; scheduled ones are batched into a digest. Pausing a notification stops delivery without losing its configuration."
        kpis={[
          { label: 'Notifications', value: records.length },
          {
            label: 'Active',
            value: countBy(records, 'status', ['Active']),
            tone: 'success',
          },
          {
            label: 'Paused',
            value: paused,
            tone: paused > 0 ? 'warning' : 'default',
          },
          { label: 'Channels', value: distinctBy(records, 'channel') },
        ]}
        columns={[
          { key: 'notification', label: 'Notification' },
          { key: 'event', label: 'Event' },
          { key: 'channel', label: 'Channel' },
          { key: 'recipients', label: 'Recipients' },
          { key: 'frequency', label: 'Frequency' },
          { key: 'status', label: 'Status' },
        ]}
        records={records}
        statusColumns={['status']}
        emptyMessage="No notification configured."
        exportFileName="notifications"
      />
    </AdminLayout>
  );
}
