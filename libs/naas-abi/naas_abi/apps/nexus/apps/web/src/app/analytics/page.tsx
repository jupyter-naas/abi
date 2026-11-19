'use client';

import { useEffect, useState } from 'react';
import { notFound, useRouter } from 'next/navigation';
import { organizationAnalyticsPath } from '@/lib/analytics-redirect';
import { useWorkspaceStore } from '@/stores/workspace';

function currentPath(): string | null {
  const { workspaces, currentWorkspaceId } = useWorkspaceStore.getState();
  return organizationAnalyticsPath(workspaces, currentWorkspaceId);
}

/**
 * The removed Analytics app's address: on to the current organization's Analytics
 * section (Organization settings › Analytics), or a 404 when no organization can be
 * told. The persisted workspaces are read first, then the API's.
 */
export default function AnalyticsRedirectPage() {
  const router = useRouter();
  // undefined: still resolving; null: no organization (404).
  const [target, setTarget] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    const resolve = async () => {
      let path = currentPath();
      if (!path) {
        try {
          await useWorkspaceStore.getState().fetchWorkspaces();
        } catch {
          // Unreachable API: no organization to go to.
        }
        path = currentPath();
      }
      if (!cancelled) setTarget(path);
    };
    const persist = useWorkspaceStore.persist;
    if (persist.hasHydrated()) void resolve();
    const unsubscribe = persist.onFinishHydration(() => void resolve());
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (target) router.replace(target);
  }, [router, target]);

  if (target === null) notFound();
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <p className="text-muted-foreground">Redirecting…</p>
    </div>
  );
}
