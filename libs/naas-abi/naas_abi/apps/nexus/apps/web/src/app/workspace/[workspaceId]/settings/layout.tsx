'use client';

import { useWorkspaceStore } from '@/stores/workspace';
import { Header } from '@/components/shell/header';

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Workspace Settings"
        subtitle={currentWorkspace?.name || 'Configure your workspace'}
      />

      <div className="flex-1 overflow-auto px-4 py-6">
        {children}
      </div>
    </div>
  );
}
