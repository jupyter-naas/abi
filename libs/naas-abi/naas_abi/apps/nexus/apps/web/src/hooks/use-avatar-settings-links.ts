'use client';

import { useWorkspaceStore } from '@/stores/workspace';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useWorkspaceSettingsAccess } from '@/hooks/use-workspace-settings-access';
import { CONSOLE_PATH, firstConsolePath, visibleConsoleGroups } from '@/app/settings/lib/nav';
import { settingsLandingPath } from '@/components/shell/settings-nav';
import { isWorkspaceSettingsPath, settingsReturnPath } from '@/lib/settings-scope-path';

export type AvatarSettingsLink = { label: string; href: string };

/** An entry whose access is still being read shows as `loading`; refused, it is null. */
export type AvatarSettingsEntry = AvatarSettingsLink | 'loading' | null;

export type AvatarSettingsLinks = {
  settings: AvatarSettingsLink;
  console: AvatarSettingsEntry;
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
  const remembered = settingsReturnPath('settings', fallback);
  const elsewhere = isWorkspaceSettingsPath(remembered) && !remembered.startsWith(`/workspace/${workspaceId}/`);
  return elsewhere ? fallback : remembered;
}

/**
 * The avatar menu's two doors: Settings (every level, `settingsLevels`) and the Console
 * (what the platform runs), the latter for whoever may watch something there. The access
 * reads are shared stores, so opening the menu again asks nothing new; mounting the avatar
 * button warms them (`useWarmAvatarSettingsLinks`).
 */
export function useAvatarSettingsLinks(): AvatarSettingsLinks {
  const settingsHref = useSettingsHref();
  const platform = usePlatformSettingsAccess();

  let consoleEntry: AvatarSettingsEntry = null;
  if (platform.status === 'checking') {
    consoleEntry = 'loading';
  } else if (platform.status === 'ready' && visibleConsoleGroups(platform.actions).length > 0) {
    consoleEntry = {
      label: 'Console',
      href: settingsReturnPath('console', firstConsolePath(platform.actions) ?? CONSOLE_PATH),
    };
  }

  return { settings: { label: 'Settings', href: settingsHref }, console: consoleEntry };
}

/** Start the access reads when the avatar button mounts, before the menu opens. */
export function useWarmAvatarSettingsLinks(): void {
  useOpenableOrganizations();
  usePlatformSettingsAccess();
}
