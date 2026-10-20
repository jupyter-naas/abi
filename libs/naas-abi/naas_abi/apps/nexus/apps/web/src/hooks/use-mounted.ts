'use client';

import { useEffect, useState } from 'react';

/**
 * False during the server render and the first client render, true after.
 *
 * Use it before rendering anything read from persisted client state (the auth
 * store rehydrates from localStorage on the client, but the server has none):
 * rendering it on the first pass makes the HTML differ and React throws a
 * hydration error.
 */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}
