'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '@/stores/auth';

export type Access = 'checking' | 'authorized' | 'denied';

/** Asks the API (not the cached user) whether this session is a platform super admin. */
export function useSuperadminAccess(): Access {
  const [access, setAccess] = useState<Access>('checking');
  useEffect(() => {
    let cancelled = false;
    authFetch('/api/admin/me')
      .then(async (res) => (res.ok ? ((await res.json()) as { is_superadmin?: boolean }) : null))
      .then((body) => !cancelled && setAccess(body?.is_superadmin ? 'authorized' : 'denied'))
      .catch(() => !cancelled && setAccess('denied'));
    return () => {
      cancelled = true;
    };
  }, []);
  return access;
}
