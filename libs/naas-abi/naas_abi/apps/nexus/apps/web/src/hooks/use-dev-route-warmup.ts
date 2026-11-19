'use client';

import { useEffect } from 'react';

const warmed = new Set<string>();

// Bumped each time the user follows an in-app link (see `noteLinkFollowed`).
let linksFollowed = 0;
let listeningForLinks = false;

/**
 * The user followed a link: warm-ups already running stop. `next dev` compiles one
 * route at a time, so the page asked for compiles next instead of after every queued
 * sibling (a scope switch from Platform settings waited ~40 s behind them).
 */
export function noteLinkFollowed(): void {
  linksFollowed += 1;
}

function listenForLinks(): void {
  if (listeningForLinks || typeof document === 'undefined') return;
  listeningForLinks = true;
  document.addEventListener(
    'click',
    (event) => {
      const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
      const href = link?.getAttribute('href');
      if (href?.startsWith('/') && !href.startsWith('//')) noteLinkFollowed();
    },
    true
  );
}

/**
 * Request each route's RSC payload once, one after another, so `next dev`
 * compiles it before the user clicks. Already-warmed routes are skipped; the rest
 * are left unwarmed once the user follows a link.
 */
export async function warmRoutes(
  hrefs: string[],
  fetchImpl: typeof fetch = fetch,
  isCancelled: () => boolean = () => false
): Promise<void> {
  const linksAtStart = linksFollowed;
  for (const href of hrefs) {
    if (isCancelled() || linksFollowed !== linksAtStart) return;
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
    listenForLinks();
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
