'use client';

import { useEffect } from 'react';

const warmed = new Set<string>();

/**
 * Request each route's RSC payload once, one after another, so `next dev`
 * compiles it before the user clicks. Already-warmed routes are skipped.
 */
export async function warmRoutes(
  hrefs: string[],
  fetchImpl: typeof fetch = fetch,
  isCancelled: () => boolean = () => false
): Promise<void> {
  for (const href of hrefs) {
    if (isCancelled()) return;
    if (warmed.has(href)) continue;
    warmed.add(href);
    try {
      await fetchImpl(href, { headers: { RSC: '1' }, credentials: 'same-origin' });
    } catch {
      // Warm-up is best effort; a failed request just means a cold compile later.
    }
  }
}

/** Test helper: forget which routes were warmed. */
export function resetWarmedRoutes(): void {
  warmed.clear();
}

/**
 * Dev-only: compile sibling routes in the background once the current page is idle.
 * In production builds every route is precompiled, so this does nothing.
 */
export function useDevRouteWarmup(hrefs: string[]): void {
  const key = hrefs.join('|');
  useEffect(() => {
    if (process.env.NODE_ENV !== 'development' || !hrefs.length) return;
    let cancelled = false;
    const start = () => void warmRoutes(hrefs, fetch, () => cancelled);
    const idle = typeof window.requestIdleCallback === 'function';
    const handle = idle ? window.requestIdleCallback(start, { timeout: 3000 }) : window.setTimeout(start, 1500);
    return () => {
      cancelled = true;
      if (idle) window.cancelIdleCallback(handle);
      else window.clearTimeout(handle);
    };
    // hrefs is captured through its joined key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}
