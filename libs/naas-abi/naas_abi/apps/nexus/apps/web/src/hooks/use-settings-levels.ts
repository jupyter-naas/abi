'use client';

import { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import { accountSettingsNavVisible } from '@/app/account/lib/nav';
import { orgSettingsNavForRole, type OrgSettingsNavItem } from '@/app/organizations/[orgId]/settings/lib/nav';
import { visiblePlatformSettingsGroups } from '@/app/settings/lib/nav';
import { organizationContainer, workspaceContainer } from '@/components/access/access-scope';
import {
  currentSettingsLevel,
  settingsLevels,
  settingsTabs,
  type SettingsLevel,
  type SettingsTab,
} from '@/components/settings/settings-levels';
import {
  SETTINGS_GROUPS,
  accessSettingsItems,
  visibleSettingsGroups,
  workspaceOrganization,
} from '@/components/shell/settings-nav';
import { useAnalyticsAccess } from '@/hooks/use-analytics-access';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useWorkspaceResourcesStore } from '@/hooks/use-workspace-resources';
import { useWorkspaceSettingsAccess } from '@/hooks/use-workspace-settings-access';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { settingsLevelReturnPath } from '@/lib/settings-scope-path';
import { useWorkspaceStore } from '@/stores/workspace';

type PageOrganization = { id: string; items: OrgSettingsNavItem[] };

/**
 * The levels of Settings the caller may open (`settingsLevels`), each read with the rule
 * its own pages apply. ``organization``: the one an organization's settings page has
 * already read (its role there, its IAM access), which wins over the current workspace's.
 *
 * ``pagesReady``: the tabs' permission reads have answered (the organization list and the
 * platform's access). A settings page waits for it, so its own data does not queue in
 * front of the tabs.
 */
export function useSettingsLevels({ organization }: { organization?: PageOrganization } = {}): {
  levels: SettingsLevel[];
  pagesReady: boolean;
} {
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === s.currentWorkspaceId));
  const flags = workspace?.featureFlags;
  const workspaceAccess = useWorkspaceSettingsAccess();
  const { status: orgsStatus, orgs } = useOpenableOrganizations();
  const { status: platformStatus, actions } = usePlatformSettingsAccess();
  // The tab list is the roles and these two reads. Resources, analytics and the access
  // pages' actions start once the tabs can paint.
  const pagesReady = orgsStatus !== 'checking' && platformStatus !== 'checking';
  // Resources are the open page's data. The column reads them when that page has, and
  // does not ask on its own: that read is what was queueing Analytics and Access.
  const resources = useWorkspaceResourcesStore((s) =>
    workspace ? (s.byWorkspace[workspace.id]?.resources ?? null) : null
  );
  const roleOpens = workspaceAccess === 'all';
  const askWorkspaceIam = pagesReady && !!workspace;
  // Each page of Access is shown to whoever IAM lets open it in the workspace.
  const { access: workspaceIam, loading: workspaceIamLoading } = useIamAccess(
    workspace ? workspaceContainer(workspaceOrganization(workspace), workspace.id) : undefined,
    undefined,
    { skip: !askWorkspaceIam }
  );
  // Analytics is listed to whoever may read the level's analytics, as each layout's own nav.
  // The role lists it until this answers.
  const workspaceAnalyticsScope =
    askWorkspaceIam && workspace ? { kind: 'workspace' as const, workspaceId: workspace.id } : null;
  const workspaceAnalyticsEntry = useAnalyticsAccess(workspaceAnalyticsScope);
  const workspaceAnalytics = workspaceAnalyticsEntry.access?.can_read === true;
  const workspaceAnalyticsKnown = !!workspaceAnalyticsScope && workspaceAnalyticsEntry.status !== 'checking';

  const workspaceOrgId = workspace?.organizationId;
  const activeId =
    organization?.id ??
    (workspaceOrgId && orgs.some((o) => o.id === workspaceOrgId) ? workspaceOrgId : null) ??
    (orgs.length === 1 ? orgs[0].id : null);
  const listed = orgs.find((o) => o.id === activeId);
  const askOrgIam = pagesReady && !!activeId && !organization;
  const { access: orgIam, loading: orgIamLoading } = useIamAccess(
    activeId && !organization ? organizationContainer(activeId) : undefined,
    undefined,
    { skip: !askOrgIam }
  );
  const orgAnalyticsScope = askOrgIam && activeId ? { kind: 'organization' as const, orgId: activeId } : null;
  const orgAnalyticsEntry = useAnalyticsAccess(orgAnalyticsScope);
  const orgAnalytics = orgAnalyticsEntry.access?.can_read === true;
  const orgAnalyticsKnown = !!orgAnalyticsScope && orgAnalyticsEntry.status !== 'checking';

  const levels = useMemo(() => {
    let workspaceGroups = null;
    if (workspace && workspaceAccess === 'all') {
      workspaceGroups = visibleSettingsGroups(resources, flags, SETTINGS_GROUPS, {
        access: workspaceIam,
        readsAnalytics: workspaceAnalytics,
        roleOpens,
        accessKnown: askWorkspaceIam && !workspaceIamLoading,
        analyticsKnown: workspaceAnalyticsKnown,
      });
    } else if (workspace && workspaceAccess === 'iam') {
      const held = accessSettingsItems(workspaceIam);
      workspaceGroups = SETTINGS_GROUPS.map((group) => ({
        ...group,
        items: group.items.filter(
          (item) => held.includes(item) || (item.needs === 'analytics' && workspaceAnalytics)
        ),
      }));
    }
    const organizationItems =
      organization?.items ??
      (listed
        ? orgSettingsNavForRole(listed.role, {
            access: orgIam,
            readsAnalytics: orgAnalytics,
            accessKnown: askOrgIam && !orgIamLoading,
            analyticsKnown: orgAnalyticsKnown,
          })
        : []);
    return settingsLevels({
      account: accountSettingsNavVisible,
      workspace: workspace && workspaceGroups ? { id: workspace.id, name: workspace.name, groups: workspaceGroups } : null,
      organization: activeId
        ? { id: activeId, name: listed?.name ?? activeId, items: organizationItems, current: activeId === workspaceOrgId }
        : null,
      otherOrganizations: orgs.filter((o) => o.id !== activeId).map((o) => ({ id: o.id, name: o.name })),
      platform: platformStatus === 'ready' ? visiblePlatformSettingsGroups(actions) : [],
    });
  }, [
    workspace,
    workspaceAccess,
    resources,
    flags,
    workspaceIam,
    workspaceIamLoading,
    workspaceAnalytics,
    workspaceAnalyticsKnown,
    roleOpens,
    organization,
    listed,
    orgIam,
    orgIamLoading,
    orgAnalytics,
    orgAnalyticsKnown,
    activeId,
    workspaceOrgId,
    orgs,
    platformStatus,
    actions,
  ]);
  return { levels, pagesReady };
}

/**
 * A Settings layout's levels: the tabs of its header (`settingsTabs`) and the level its
 * column lists, the page's. ``mobile``: a tab opens its level's list.
 */
export function useSettingsTabs({
  organization,
  mobile,
}: {
  organization?: PageOrganization;
  mobile: boolean;
}): { tabs: SettingsTab[]; level: SettingsLevel | null; pagesReady: boolean } {
  const pathname = usePathname() ?? '';
  const { levels, pagesReady } = useSettingsLevels({ organization });
  const view = useMemo(
    () => ({
      tabs: settingsTabs(levels, pathname, { mobile, lastVisited: settingsLevelReturnPath }),
      level: currentSettingsLevel(levels, pathname),
      pagesReady,
    }),
    [levels, pathname, mobile, pagesReady]
  );
  return view;
}
