'use client';

import { useWorkspaceStore } from '@/stores/workspace';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useWorkspaceSettingsAccessView } from '@/hooks/use-workspace-settings-access';
import { settingsLandingPath } from '@/components/shell/settings-nav';
import { isWorkspaceSettingsPath, settingsLevelReturnPath, settingsReturnPath } from '@/lib/settings-scope-path';
import { orgSettingsIndexPath } from '@/app/organizations/[orgId]/settings/lib/nav';
import { firstPlatformSettingsPath, PLATFORM_SETTINGS_INDEX, visiblePlatformSettingsGroups } from '@/app/settings/lib/nav';

export type AvatarSettingsLink = { label: string; href: string };

/** A level whose access is still being read shows as `loading`; refused, it is null. */
export type AvatarSettingsEntry = AvatarSettingsLink | 'loading' | null;

export type AvatarSettingsLinks = {
  account: AvatarSettingsLink;
  organization: AvatarSettingsEntry;
  platform: AvatarSettingsEntry;
};

/**
 * The account menu's settings rows: Account, Organization, Platform, each at the level's last
 * page (``settingsLevelReturnPath``), else its first. Both access reads are shared stores, so
 * opening the menu again asks nothing new; mounting the avatar warms them.
 */
export function useAvatarSettingsLinks(): AvatarSettingsLinks {
  const organizations = useOpenableOrganizations();
  const platformSettings = usePlatformSettingsAccess();
  const workspaceOrgId = useWorkspaceStore((s) =>
    s.workspaces.find((w) => w.id === s.currentWorkspaceId)?.organizationId
  );

  let organization: AvatarSettingsEntry = null;
  if (organizations.status === 'checking') {
    organization = 'loading';
  } else {
    const open = organizations.orgs;
    const pick =
      (workspaceOrgId && open.find((o) => o.id === workspaceOrgId)) || (open.length === 1 ? open[0] : null);
    if (pick) {
      const remembered = settingsLevelReturnPath('organization');
      organization = {
        label: 'Organization',
        href:
          remembered && remembered.startsWith(`/organizations/${pick.id}/`)
            ? remembered
            : orgSettingsIndexPath(pick.id),
      };
    }
  }

  let platform: AvatarSettingsEntry = null;
  if (platformSettings.status === 'checking') {
    platform = 'loading';
  } else if (platformSettings.status === 'ready' && visiblePlatformSettingsGroups(platformSettings.actions).length > 0) {
    platform = {
      label: 'Platform',
      href:
        settingsLevelReturnPath('platform') ??
        firstPlatformSettingsPath(platformSettings.actions) ??
        PLATFORM_SETTINGS_INDEX,
    };
  }

  return {
    account: { label: 'Account', href: settingsLevelReturnPath('account') ?? '/account/profile' },
    organization,
    platform,
  };
}

/**
 * Where the dock's Settings opens: the last settings page, at any level, else this
 * workspace's settings when the caller opens them, else their account. A page of another
 * workspace's settings is not reopened from this one.
 */
export function useSettingsHref(): string {
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { access, iam } = useWorkspaceSettingsAccessView();
  const opensWorkspace = !!workspaceId && (access === 'all' || access === 'iam');
  const fallback = opensWorkspace ? `/workspace/${workspaceId}${settingsLandingPath(access, iam)}` : '/account/profile';
  const remembered = settingsReturnPath(fallback);
  const elsewhere = isWorkspaceSettingsPath(remembered) && !remembered.startsWith(`/workspace/${workspaceId}/`);
  return elsewhere ? fallback : remembered;
}

/**
 * Start the access reads the Settings tabs need (`useSettingsLevels`) when the avatar
 * mounts: they are shared stores, so Settings opens with its tabs already known.
 */
export function useWarmAvatarSettingsLinks(): void {
  useOpenableOrganizations();
  usePlatformSettingsAccess();
}
