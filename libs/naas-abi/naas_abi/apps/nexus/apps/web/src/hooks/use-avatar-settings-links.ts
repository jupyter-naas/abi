'use client';

import { orgSettingsIndexPath } from '@/app/organizations/[orgId]/settings/lib/nav';
import { useWorkspaceStore } from '@/stores/workspace';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { firstPlatformSettingsPath, PLATFORM_SETTINGS_INDEX, visiblePlatformSettingsGroups } from '@/app/settings/lib/nav';
import { settingsScopeReturnPath } from '@/lib/settings-scope-path';

/** ``detail``: what the link opens, when the label alone does not say (the organization's name). */
export type AvatarSettingsLink = { label: string; href: string; detail?: string };

/** A scope whose access is still being read shows as `loading`; refused, it is null. */
export type AvatarSettingsEntry = AvatarSettingsLink | 'loading' | null;

export type AvatarSettingsLinks = {
  account: AvatarSettingsLink;
  organization: AvatarSettingsEntry;
  platform: AvatarSettingsEntry;
};

/**
 * Avatar menu destinations: Account, Organization, Platform, at the same remembered
 * paths as the settings scope switcher. Both access reads are shared stores, so opening
 * the menu again asks nothing new; mounting the avatar button warms them
 * (`useWarmAvatarSettingsLinks`).
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
      (workspaceOrgId && open.find((o) => o.id === workspaceOrgId)) ||
      (open.length === 1 ? open[0] : null);
    if (pick) {
      organization = {
        label: 'Organization',
        href: settingsScopeReturnPath({ kind: 'organization', orgId: pick.id }, orgSettingsIndexPath(pick.id)),
        detail: pick.name,
      };
    }
  }

  let platform: AvatarSettingsEntry = null;
  if (platformSettings.status === 'checking') {
    platform = 'loading';
  } else if (
    platformSettings.status === 'ready' &&
    visiblePlatformSettingsGroups(platformSettings.actions).length > 0
  ) {
    platform = {
      label: 'Platform',
      href: settingsScopeReturnPath(
        { kind: 'platform' },
        firstPlatformSettingsPath(platformSettings.actions) ?? PLATFORM_SETTINGS_INDEX
      ),
    };
  }

  return {
    account: { label: 'Account', href: settingsScopeReturnPath({ kind: 'account' }, '/account/profile') },
    organization,
    platform,
  };
}

/** Start both access reads when the avatar button mounts, before the menu opens. */
export function useWarmAvatarSettingsLinks(): void {
  useOpenableOrganizations();
  usePlatformSettingsAccess();
}
