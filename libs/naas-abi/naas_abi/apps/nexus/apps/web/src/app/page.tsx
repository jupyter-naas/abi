'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { useWorkspacesReady } from '@/hooks/use-workspaces-ready';
import { PlatformLoader } from '@/components/shell/platform-loader';

export default function Home() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { workspaces, currentWorkspaceId } = useWorkspaceStore();
  // Where to go is decided once the API answered the workspaces: a platform still starting
  // keeps this loader (retrying), never sends someone to "no workspace".
  const { ready: checked, retrying } = useWorkspacesReady(!!user);

  useEffect(() => {
    if (!user) router.replace('/auth/login');
  }, [router, user]);

  useEffect(() => {
    if (!user || !checked) return;
    const targetWorkspaceId = currentWorkspaceId || workspaces[0]?.id;
    if (targetWorkspaceId) {
      router.replace(`/workspace/${targetWorkspaceId}/chat`);
    } else {
      router.replace('/no-workspace');
    }
  }, [router, user, currentWorkspaceId, workspaces, checked]);

  return <PlatformLoader retrying={retrying} />;
}
