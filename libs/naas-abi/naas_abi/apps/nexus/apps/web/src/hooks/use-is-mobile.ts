'use client';

import { useEffect, useState } from 'react';

/** Tailwind `md` breakpoint: below this we use the mobile shell. */
export const MOBILE_BREAKPOINT_PX = 768;

/**
 * True when the viewport is below `md`. SSR-safe: starts false, then updates
 * after mount so desktop hydration is not forced into the mobile tree.
 */
export function useIsMobile(breakpointPx: number = MOBILE_BREAKPOINT_PX): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpointPx - 1}px)`);
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, [breakpointPx]);

  return isMobile;
}
