'use client';

import { useWorkspaceStore } from '@/stores/workspace';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useWorkspaceSettingsAccessView } from '@/hooks/use-workspace-settings-access';
import { settingsLandingPath } from '@/components/shell/settings-nav';
import { isWorkspaceSettingsPath, settingsReturnPath } from '@/lib/settings-scope-path';

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
