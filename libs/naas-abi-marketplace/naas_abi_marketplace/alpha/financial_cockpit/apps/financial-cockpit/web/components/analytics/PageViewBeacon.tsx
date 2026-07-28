'use client';

import { useEffect } from 'react';

type Props = {
  /** Analytics page key — path without leading slash + filter query. */
  page: string;
  /** Entity url_slug; null on admin pages. */
  perimeter?: string | null;
};

/**
 * Fire-and-forget page-view ping. Keyed on the analytics `page` (+ perimeter)
 * so it fires on real navigations and filter changes (scenario/company), not
 * on `router.refresh()` which keeps the same page key.
 */
export function PageViewBeacon({ page, perimeter = null }: Props) {
  useEffect(() => {
    if (!page) return;
    fetch('/api/analytics/pageview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page, perimeter }),
      keepalive: true,
    }).catch(() => {
      /* best-effort telemetry */
    });
  }, [page, perimeter]);

  return null;
}
