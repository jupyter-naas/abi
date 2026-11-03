'use client';

import { useCallback, useEffect, useMemo } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { Header } from '@/components/shell/header';
import {
  SETTINGS_GROUPS,
  settingsItemFor,
  settingsItemShown,
  settingsLandingPath,
  settingsPageOpens,
} from '@/components/shell/settings-nav';
import { SettingsNoAccess } from '@/components/settings/settings-no-access';
import { useWorkspaceSettingsAccess } from '@/hooks/use-workspace-settings-access';
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
  // A page of something the caller may not use here has nothing to manage.
  // Read again each time the settings open: a module or a policy changed since shows.
  const { resources } = useWorkspaceResources(workspaceId, { refresh: true });
  const item = settingsItemFor(pathname ?? '');
  const outsideSet = Boolean(item && resources && !settingsItemShown(item, resources));
  // Who may open these pages at all: the dock's rule (useWorkspaceSettingsAccess). Someone
  // who holds only `iam:` rights here goes to Roles & permissions; anyone else is told no.
  const access = useWorkspaceSettingsAccess();
  const opens = settingsPageOpens(access, pathname ?? '');
  const router = useRouter();
  useEffect(() => {
    if (access === 'iam' && opens === false && workspaceId) {
      router.replace(`/workspace/${workspaceId}${settingsLandingPath(access)}`);
    }
  }, [access, opens, workspaceId, router]);
  const page =
    opens === null || (access === 'iam' && opens === false) ? null : opens === false ? (
      <SettingsNoAccess of="workspace" />
    ) : outsideSet && item && resources ? (
      <NotInWorkspace label={item.label} />
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
