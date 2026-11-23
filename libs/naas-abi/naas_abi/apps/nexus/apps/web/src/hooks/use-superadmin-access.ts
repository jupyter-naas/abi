'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '@/stores/auth';
import { usePermissionRevision, usePermissionSessionKey } from '@/lib/permission-cache';

export type SuperadminAccess = 'checking' | 'authorized' | 'denied';

/** Asks the API whether the current user is a platform superadmin (Settings > Services). */
export function useSuperadminAccess(): SuperadminAccess {
  const session = usePermissionSessionKey();
  const revision = usePermissionRevision();
  const [answer, setAnswer] = useState<{ session: string; access: SuperadminAccess } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch('/api/admin/me');
        if (!res.ok) {
          if (!cancelled) setAnswer({ session, access: 'denied' });
          return;
        }
        const data = await res.json();
        if (!cancelled) setAnswer({ session, access: data.is_superadmin ? 'authorized' : 'denied' });
      } catch {
        if (!cancelled) setAnswer({ session, access: 'denied' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session, revision]);

  return answer?.session === session ? answer.access : 'checking';
}
