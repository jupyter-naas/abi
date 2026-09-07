'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';

export default function Home() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { workspaces, currentWorkspaceId, fetchWorkspaces } = useWorkspaceStore();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!user) {
      router.replace('/auth/login');
      return;
    }
    let cancelled = false;
    void fetchWorkspaces().finally(() => {
      if (!cancelled) setChecked(true);
    });
    return () => {
      cancelled = true;
    };
  }, [router, user, fetchWorkspaces]);

  useEffect(() => {
    if (!user || !checked) return;
    const targetWorkspaceId = currentWorkspaceId || workspaces[0]?.id;
    if (targetWorkspaceId) {
      router.replace(`/workspace/${targetWorkspaceId}/chat`);
    } else {
      router.replace('/no-workspace');
    }
  }, [router, user, currentWorkspaceId, workspaces, checked]);

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center">
        <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto" />
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}
