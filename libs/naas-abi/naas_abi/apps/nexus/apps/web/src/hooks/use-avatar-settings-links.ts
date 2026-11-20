'use client';

import { useWorkspaceStore } from '@/stores/workspace';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useWorkspaceSettingsAccess } from '@/hooks/use-workspace-settings-access';
import { settingsLandingPath } from '@/components/shell/settings-nav';
import { isWorkspaceSettingsPath, settingsReturnPath } from '@/lib/settings-scope-path';

export type AvatarSettingsLink = { label: string; href: string };

export type AvatarSettingsLinks = {
  settings: AvatarSettingsLink;
};

/**
 * Where Settings opens: the last settings page, at any level, else this workspace's
 * settings when the caller opens them, else their account. A page of another
 * workspace's settings is not reopened from this one.
 */
export function useSettingsHref(): string {
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const access = useWorkspaceSettingsAccess();
  const opensWorkspace = !!workspaceId && (access === 'all' || access === 'iam');
  const fallback = opensWorkspace ? `/workspace/${workspaceId}${settingsLandingPath(access)}` : '/account/profile';
  const remembered = settingsReturnPath(fallback);
  const elsewhere = isWorkspaceSettingsPath(remembered) && !remembered.startsWith(`/workspace/${workspaceId}/`);
  return elsewhere ? fallback : remembered;
}

/**
 * The avatar menu's door to Settings, every level in its tabs (`settingsLevels`), like the
 * dock's. The levels' access reads are shared stores, so opening Settings asks nothing
 * new; mounting the avatar button warms them (`useWarmAvatarSettingsLinks`).
 */
export function useAvatarSettingsLinks(): AvatarSettingsLinks {
  return { settings: { label: 'Settings', href: useSettingsHref() } };
}

/** Start the access reads when the avatar button mounts, before the menu opens. */
export function useWarmAvatarSettingsLinks(): void {
  useOpenableOrganizations();
  usePlatformSettingsAccess();
}
