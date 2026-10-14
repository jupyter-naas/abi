'use client';

import { useMemo } from 'react';
import { useParams, usePathname } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { Header } from '@/components/shell/header';
import { SETTINGS_GROUPS } from '@/components/shell/settings-nav';
import { useDevRouteWarmup } from '@/hooks/use-dev-route-warmup';
import { SettingsReloadProvider } from '@/components/settings/settings-reload';

// Service embeds and the architecture view manage their own viewport.
// Every other settings page scrolls in the padded area beside the settings nav.
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
  const fetchWorkspaces = useWorkspaceStore((state) => state.fetchWorkspaces);
  const isFullPage = FULL_PAGE_PATTERN.test(pathname ?? '');
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const settingsHrefs = useMemo(
    () =>
      workspaceId
        ? SETTINGS_GROUPS.flatMap((group) => group.items.map((item) => `/workspace/${workspaceId}${item.href}`))
        : [],
    [workspaceId]
  );
  useDevRouteWarmup(settingsHrefs);

  return (
    <div className="flex h-full flex-col">
      {!pathname?.endsWith('/settings/infrastructure') && <Header
        title="Settings"
        subtitle={currentWorkspace?.name || 'Configure your workspace'}
      />}

      <SettingsReloadProvider onReload={fetchWorkspaces}>
        {isFullPage ? (
          <div className="flex-1 overflow-hidden">{children}</div>
        ) : (
          <div className="flex-1 overflow-auto px-4 py-6">
            <div className="w-full min-w-0">{children}</div>
          </div>
        )}
      </SettingsReloadProvider>
    </div>
  );
}
