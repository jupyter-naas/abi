'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '@/stores/auth';

export type SuperadminAccess = 'checking' | 'authorized' | 'denied';

/** Asks the API whether the current user is a platform superadmin (Settings > Services). */
export function useSuperadminAccess(): SuperadminAccess {
  const [access, setAccess] = useState<SuperadminAccess>('checking');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch('/api/admin/me');
        if (!res.ok) {
          if (!cancelled) setAccess('denied');
          return;
        }
        const data = await res.json();
        if (!cancelled) setAccess(data.is_superadmin ? 'authorized' : 'denied');
      } catch {
        if (!cancelled) setAccess('denied');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return access;
}
