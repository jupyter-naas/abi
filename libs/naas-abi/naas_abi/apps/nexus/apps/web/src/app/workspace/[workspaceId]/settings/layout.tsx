'use client';

import { usePathname } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { Header } from '@/components/shell/header';

// Service embeds and architecture visualization use the full content area instead of
// the centered card layout every other settings page uses.
const FULL_PAGE_PATTERN = /\/settings\/(?:services\/[^/]+|infrastructure)$/;

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
  const pathname = usePathname();
  const isFullPage = FULL_PAGE_PATTERN.test(pathname ?? '');

  return (
    <div className="flex h-full flex-col">
      {!pathname?.endsWith('/settings/infrastructure') && <Header
        title="Settings"
        subtitle={currentWorkspace?.name || 'Configure your workspace'}
      />}

      {isFullPage ? (
        <div className="flex-1 overflow-hidden">{children}</div>
      ) : (
        <div className="flex-1 overflow-auto px-4 py-6">
          <div className="mx-auto max-w-4xl">{children}</div>
        </div>
      )}
    </div>
  );
}
