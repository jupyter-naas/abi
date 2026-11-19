'use client';

import { useMemo } from 'react';
import { accountSettingsNavVisible } from '@/app/account/lib/nav';
import { orgSettingsNavForRole, type OrgSettingsNavItem } from '@/app/organizations/[orgId]/settings/lib/nav';
import { visibleAdministrationItems } from '@/app/settings/lib/nav';
import { opensRolesAndPermissions } from '@/components/access/access-sections';
import { organizationContainer, workspaceContainer } from '@/components/access/access-scope';
import { settingsLevels, type SettingsLevel } from '@/components/settings/settings-levels';
import { SETTINGS_GROUPS, visibleSettingsGroups, workspaceOrganization } from '@/components/shell/settings-nav';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useWorkspaceResources } from '@/hooks/use-workspace-resources';
import { useWorkspaceSettingsAccess } from '@/hooks/use-workspace-settings-access';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { useWorkspaceStore } from '@/stores/workspace';

/**
 * The levels of Settings the caller may open (`settingsLevels`), each read with the rule
 * its own pages apply. ``organization``: the one an organization's settings page has
 * already read (its role there, its IAM access), which wins over the current workspace's.
 */
export function useSettingsLevels({
  organization,
}: { organization?: { id: string; items: OrgSettingsNavItem[] } } = {}): SettingsLevel[] {
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === s.currentWorkspaceId));
  const flags = workspace?.featureFlags;
  const workspaceAccess = useWorkspaceSettingsAccess();
  const { resources } = useWorkspaceResources(workspace?.id);
  // Roles & permissions is shown to whoever would see a section of it in the workspace.
  const { access: workspaceIam } = useIamAccess(
    workspace ? workspaceContainer(workspaceOrganization(workspace), workspace.id) : undefined,
    undefined,
    { skip: !workspace }
  );
  const holdsWorkspaceIam = !!workspace && opensRolesAndPermissions(workspaceIam);

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

  const { status: platformStatus, actions } = usePlatformSettingsAccess();

  return useMemo(() => {
    let workspaceGroups = null;
    if (workspace && workspaceAccess === 'all') {
      workspaceGroups = visibleSettingsGroups(resources, flags, SETTINGS_GROUPS, { holdsIam: holdsWorkspaceIam });
    } else if (workspace && workspaceAccess === 'iam') {
      workspaceGroups = SETTINGS_GROUPS.map((group) => ({
        ...group,
        items: group.items.filter((item) => item.needs === 'iam'),
      }));
    }
    const organizationItems =
      organization?.items ??
      (listed ? orgSettingsNavForRole(listed.role, { holdsIam: opensRolesAndPermissions(orgIam) }) : []);
    return settingsLevels({
      account: accountSettingsNavVisible,
      workspace: workspace && workspaceGroups ? { id: workspace.id, groups: workspaceGroups } : null,
      organization: activeId ? { id: activeId, name: listed?.name ?? activeId, items: organizationItems } : null,
      otherOrganizations: orgs.filter((o) => o.id !== activeId).map((o) => ({ id: o.id, name: o.name })),
      platform: platformStatus === 'ready' ? visibleAdministrationItems(actions) : [],
    });
  }, [
    workspace,
    workspaceAccess,
    resources,
    flags,
    holdsWorkspaceIam,
    organization,
    listed,
    orgIam,
    activeId,
    orgs,
    platformStatus,
    actions,
  ]);
}
