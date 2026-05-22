'use client';

import { usePathname } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { trackPageView } from '@/lib/analytics-tracking';

// Wait for tenant-context.tsx to finish rewriting document.title (it
// re-applies at 100/300/600ms) so the tracked page_title reflects the
// destination page, not the previous one.
const TITLE_SETTLE_MS = 700;

function getWorkspaceId(pathname: string): string | undefined {
  const match = pathname.match(/^\/workspace\/([^/]+)/);
  return match ? match[1] : undefined;
}

export function AnalyticsPageTracker() {
  const pathname = usePathname();
  const lastTrackedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname || lastTrackedRef.current === pathname) return;
    lastTrackedRef.current = pathname;

    const handle = setTimeout(() => {
      trackPageView({
        page_path: pathname,
        page_title: document.title,
        workspace_id: getWorkspaceId(pathname),
      });
    }, TITLE_SETTLE_MS);

    return () => clearTimeout(handle);
  }, [pathname]);

  return null;
}
