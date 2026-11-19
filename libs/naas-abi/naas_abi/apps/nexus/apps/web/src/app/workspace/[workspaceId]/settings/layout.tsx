'use client';

import { useCallback, useEffect } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  settingsItemFor,
  settingsItemShown,
  settingsLandingPath,
  settingsPageOpens,
} from '@/components/shell/settings-nav';
import { SettingsNoAccess } from '@/components/settings/settings-no-access';
import { SettingsLevelsNav } from '@/components/settings/settings-levels-nav';
import { SettingsLayoutRoot, useWorkspaceReturnPath } from '@/components/settings/settings-shell';
import { SettingsShellHeader } from '@/components/settings/settings-shell-header';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useRememberSettingsPath } from '@/hooks/use-remember-settings-scope';
import { useWorkspaceSettingsAccess } from '@/hooks/use-workspace-settings-access';
import { reloadWorkspaceResources, useWorkspaceResources } from '@/hooks/use-workspace-resources';
import { SettingsReloadProvider } from '@/components/settings/settings-reload';
import { NotInWorkspace } from './not-in-workspace';
import '@/app/organizations/[orgId]/settings/org-settings-layout.css';

// Service embeds use the whole content area instead of the centered column every
// other settings page uses.
const SERVICE_PAGE_PATTERN = /\/settings\/services\/[^/]+$/;

const INDEX_PATTERN = /^\/workspace\/[^/]+\/settings\/?$/;

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname() ?? '';
  const router = useRouter();
  const isMobile = useIsMobile();
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const theme = useWorkspaceStore((state) => state.workspaces.find((w) => w.id === workspaceId)?.theme);
  const fetchWorkspaces = useWorkspaceStore((state) => state.fetchWorkspaces);
  const isFullPage = SERVICE_PAGE_PATTERN.test(pathname);
  const isIndex = INDEX_PATTERN.test(pathname);
  const showMobileList = isMobile && isIndex;
  const showMobileDetail = isMobile && !isIndex;

  // Reload: the workspaces and what this one has.
  const reload = useCallback(
    () => Promise.all([fetchWorkspaces(), reloadWorkspaceResources(workspaceId)]),
    [fetchWorkspaces, workspaceId]
  );
  // A page of something the caller may not use here has nothing to manage.
  // Read again each time the settings open: a module or a policy changed since shows.
  const { resources } = useWorkspaceResources(workspaceId, { refresh: true });
  const item = settingsItemFor(pathname);
  // Only a page of the column is reopened: not the index, nor a former URL that redirects.
  useRememberSettingsPath(item ? pathname : null);
  const outsideSet = Boolean(item && resources && !settingsItemShown(item, resources));
  // Who may open these pages at all: the dock's rule (useWorkspaceSettingsAccess). Someone
  // who holds only `iam:` rights here goes to Roles & permissions; anyone else is told no.
  const access = useWorkspaceSettingsAccess();
  const opens = isIndex ? true : settingsPageOpens(access, pathname);
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

  const workspaceHref = useWorkspaceReturnPath(
    workspaceId ? `/workspace/${workspaceId}/chat` : '/',
    workspaceId
  );
  const handleBack = () => {
    if (showMobileDetail && workspaceId) {
      router.push(`/workspace/${workspaceId}/settings`);
      return;
    }
    router.push(workspaceHref);
  };

  return (
    <SettingsLayoutRoot brand={{ primary: theme?.primaryColor ?? null, accent: theme?.accentColor ?? null }}>
      <div className="org-settings-layout-left">
        <SettingsShellHeader
          detailTitle={showMobileDetail ? (item?.label ?? null) : null}
          onBack={handleBack}
          backAriaLabel={showMobileDetail ? 'Back to settings' : 'Back to workspace'}
        />

        <div
          data-org-settings-body=""
          className={
            showMobileList
              ? 'org-settings-layout-body org-settings-layout-body-mobile-list'
              : showMobileDetail
                ? 'org-settings-layout-body org-settings-layout-body-mobile-detail'
                : 'org-settings-layout-body'
          }
        >
          {!showMobileDetail && <SettingsLevelsNav mobileList={showMobileList} />}

          {!showMobileList && (
            <SettingsReloadProvider onReload={reload}>
              <div className={isFullPage ? 'org-settings-layout-main settings-main-full' : 'org-settings-layout-main'}>
                <div
                  className={
                    isFullPage ? 'org-settings-layout-content settings-content-full' : 'org-settings-layout-content'
                  }
                >
                  {page}
                </div>
              </div>
            </SettingsReloadProvider>
          )}
        </div>
      </div>
    </SettingsLayoutRoot>
  );
}
