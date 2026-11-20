'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { SettingsLoading } from '@/components/settings/settings-ui';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { ACCESS_ITEMS, holds } from '../lib/nav';

/** Platform › Access: the first of its pages the caller holds (an old Roles & permissions
 *  link that named no section lands here). */
export default function PlatformAccessIndex() {
  const router = useRouter();
  const { status, actions } = usePlatformSettingsAccess();
  const first = status === 'ready' ? ACCESS_ITEMS.find((item) => holds(item.needs, actions)) : undefined;
  useEffect(() => {
    if (first) router.replace(first.href);
  }, [first, router]);
  if (status === 'ready' && !first) {
    return (
      <p className="org-settings-empty-body" role="status">
        You cannot manage access on the platform.
      </p>
    );
  }
  return <SettingsLoading />;
}
