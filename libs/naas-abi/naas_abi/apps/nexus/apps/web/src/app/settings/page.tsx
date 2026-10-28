'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { firstPlatformSettingsPath } from './lib/nav';

/**
 * `/settings`: a computer opens the first page the caller may open; a phone stays
 * here, where the layout lists the pages (list, then page). With none, the layout
 * shows the 403.
 */
export default function PlatformSettingsIndexPage() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const { status, actions } = usePlatformSettingsAccess();

  useEffect(() => {
    if (isMobile || status !== 'ready') return;
    const first = firstPlatformSettingsPath(actions);
    if (first) router.replace(first);
  }, [isMobile, status, actions, router]);

  return null;
}
