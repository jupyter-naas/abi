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
import { useReadsAnalytics } from '@/hooks/use-analytics-access';
import { useDevRouteWarmup } from '@/hooks/use-dev-route-warmup';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useWorkspaceResources } from '@/hooks/use-workspace-resources';
import { useWorkspaceSettingsAccess } from '@/hooks/use-workspace-settings-access';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { settingsLevelReturnPath } from '@/lib/settings-scope-path';
import { useWorkspaceStore } from '@/stores/workspace';

type PageOrganization = { id: string; items: OrgSettingsNavItem[] };

/**
 * The levels of Settings the caller may open (`settingsLevels`), each read with the rule
 * its own pages apply. ``organization``: the one an organization's settings page has
 * already read (its role there, its IAM access), which wins over the current workspace's.
 */
export function useSettingsLevels({ organization }: { organization?: PageOrganization } = {}): SettingsLevel[] {
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === s.currentWorkspaceId));
  const flags = workspace?.featureFlags;
  const workspaceAccess = useWorkspaceSettingsAccess();
  const { resources } = useWorkspaceResources(workspace?.id);
  // Each page of Access is shown to whoever IAM lets open it in the workspace.
  const { access: workspaceIam } = useIamAccess(
    workspace ? workspaceContainer(workspaceOrganization(workspace), workspace.id) : undefined,
    undefined,
    { skip: !workspace }
  );
  // Analytics is listed to whoever may read the level's analytics, as each layout's own nav.
  const workspaceAnalytics = useReadsAnalytics(workspace ? { kind: 'workspace', workspaceId: workspace.id } : null);

  const { orgs } = useOpenableOrganizations();
  const workspaceOrgId = workspace?.organizationId;
  const activeId =
    organization?.id ??
    (workspaceOrgId && orgs.some((o) => o.id === workspaceOrgId) ? workspaceOrgId : null) ??
    (orgs.length === 1 ? orgs[0].id : null);
  const listed = orgs.find((o) => o.id === activeId);
  const { access: orgIam } = useIamAccess(
    activeId && !organization ? organizationContainer(activeId) : undefined,
    undefined,
    { skip: !activeId || !!organization }
  );
  const orgAnalytics = useReadsAnalytics(activeId && !organization ? { kind: 'organization', orgId: activeId } : null);

  const { status: platformStatus, actions } = usePlatformSettingsAccess();

  return useMemo(() => {
    let workspaceGroups = null;
    if (workspace && workspaceAccess === 'all') {
      workspaceGroups = visibleSettingsGroups(resources, flags, SETTINGS_GROUPS, {
        access: workspaceIam,
        readsAnalytics: workspaceAnalytics,
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
      (listed ? orgSettingsNavForRole(listed.role, { access: orgIam, readsAnalytics: orgAnalytics }) : []);
    return settingsLevels({
      account: accountSettingsNavVisible,
      workspace: workspace && workspaceGroups ? { id: workspace.id, groups: workspaceGroups } : null,
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
    workspaceAnalytics,
    organization,
    listed,
    orgIam,
    orgAnalytics,
    activeId,
    workspaceOrgId,
    orgs,
    platformStatus,
    actions,
  ]);
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
}): { tabs: SettingsTab[]; level: SettingsLevel | null } {
  const pathname = usePathname() ?? '';
  const levels = useSettingsLevels({ organization });
  const view = useMemo(
    () => ({
      tabs: settingsTabs(levels, pathname, { mobile, lastVisited: settingsLevelReturnPath }),
      level: currentSettingsLevel(levels, pathname),
    }),
    [levels, pathname, mobile]
  );
  const hrefs = useMemo(
    () => [
      ...view.tabs.filter((tab) => !tab.active).map((tab) => tab.href),
      ...(view.level?.groups.flatMap((group) => group.links.map((l) => l.href)) ?? []),
    ],
    [view]
  );
  useDevRouteWarmup(hrefs);
  return view;
}
