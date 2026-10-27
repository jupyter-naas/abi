'use client';

import { useCallback, useMemo } from 'react';
import { useParams, usePathname } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { Header } from '@/components/shell/header';
import { SETTINGS_GROUPS, settingsItemFor, settingsItemShown } from '@/components/shell/settings-nav';
import { useDevRouteWarmup } from '@/hooks/use-dev-route-warmup';
import { reloadWorkspaceResources, useWorkspaceResources } from '@/hooks/use-workspace-resources';
import { SettingsReloadProvider } from '@/components/settings/settings-reload';
import { NotInWorkspace } from './not-in-workspace';

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
  // Reload: the workspaces and what this one has.
  const reload = useCallback(
    () => Promise.all([fetchWorkspaces(), reloadWorkspaceResources(workspaceId)]),
    [fetchWorkspaces, workspaceId]
  );
  // A page of something outside the workspace's set has nothing to manage here.
  // Read again each time the settings open: a set changed on Modules & features shows.
  const { resources } = useWorkspaceResources(workspaceId, { refresh: true });
  const item = settingsItemFor(pathname ?? '');
  const outsideSet = Boolean(item && resources && !settingsItemShown(item, resources));
  const page = outsideSet && item && resources ? (
    <NotInWorkspace label={item.label} resources={resources} workspaceId={workspaceId ?? ''} />
  ) : (
    children
  );

  return (
    <div className="flex h-full flex-col">
      {!pathname?.endsWith('/settings/infrastructure') && <Header
        title="Settings"
        subtitle={currentWorkspace?.name || 'Configure your workspace'}
      />}

      <SettingsReloadProvider onReload={reload}>
        {isFullPage ? (
          <div className="flex-1 overflow-hidden">{page}</div>
        ) : (
          <div className="flex-1 overflow-auto px-4 py-6">
            <div className="mx-auto max-w-4xl">{page}</div>
          </div>
        )}
      </SettingsReloadProvider>
    </div>
  );
}
