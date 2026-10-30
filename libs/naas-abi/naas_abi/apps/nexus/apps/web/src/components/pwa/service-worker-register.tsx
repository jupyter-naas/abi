'use client';

import { useEffect } from 'react';

/**
 * Registers the network-only service worker when supported (HTTPS or localhost).
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!('serviceWorker' in navigator)) return;
    if (process.env.NODE_ENV !== 'production') return;

    void navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
      // Installability is best-effort; manifest still enables iOS Add to Home Screen.
    });
  }, []);

  return null;
}
