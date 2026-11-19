'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isMobileViewport, useIsMobile } from '@/hooks/use-is-mobile';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { firstConsolePath } from '../lib/nav';

/**
 * `/settings/console`: a computer opens the Console's first page the caller may open;
 * a phone stays here, where the layout lists the Console. With none, the layout shows
 * the 403.
 */
export default function ConsoleIndexPage() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const { status, actions } = usePlatformSettingsAccess();

  useEffect(() => {
    if (isMobile || isMobileViewport() || status !== 'ready') return;
    const first = firstConsolePath(actions);
    if (first) router.replace(first);
  }, [isMobile, status, actions, router]);

  return null;
}
