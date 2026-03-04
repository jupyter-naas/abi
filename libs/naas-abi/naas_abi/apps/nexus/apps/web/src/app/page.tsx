'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';

export default function Home() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { workspaces, currentWorkspaceId } = useWorkspaceStore();

  useEffect(() => {
    // If not logged in, redirect to login
    if (!user) {
      router.replace('/auth/login');
      return;
    }

    // If logged in, redirect to workspace
    const targetWorkspaceId = currentWorkspaceId || workspaces[0]?.id;
    if (targetWorkspaceId) {
      router.replace(`/workspace/${targetWorkspaceId}/chat`);
    } else {
      // No workspaces available, redirect to login (edge case)
      router.replace('/auth/login');
    }
  }, [router, user, currentWorkspaceId, workspaces]);

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center">
        <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto" />
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}
