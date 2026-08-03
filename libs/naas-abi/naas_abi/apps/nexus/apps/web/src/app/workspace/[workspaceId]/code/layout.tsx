'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { useCodeStore, useEnsureSelectedRepo } from '@/stores/code';
import { usePlatformStatusStore } from '@/stores/platform-status';

// The Code sub-app navigation (Workspaces / Branches / Pull requests + repo
// selector) lives in the left section panel (see code-section.tsx), like the
// Knowledge Graph section. We still render the shared top Header for Abi + user
// menu. Branch / API / Coder live in PlatformStatusFooter.
export default function CodeLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  useEnsureSelectedRepo(workspaceId);

  useEffect(() => {
    usePlatformStatusStore.getState().setRefresh({
      onRefresh: () => {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('nexus-code-refresh'));
        }
      },
      title: 'Refresh Code view',
    });
    return () => {
      usePlatformStatusStore.getState().clearRefresh();
      useCodeStore.getState().clearRuntimeMeta();
    };
  }, []);

  return (
    <div className="flex h-full flex-col">
      <Header title="Code" />
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}
