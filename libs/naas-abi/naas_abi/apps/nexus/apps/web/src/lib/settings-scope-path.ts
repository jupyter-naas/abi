/**
 * The last Settings page and the last Console page visited (sessionStorage), so the
 * avatar menu and the dock reopen where the caller left off.
 */

export type SettingsScopeKey =
  | { kind: 'account' }
  | { kind: 'platform' }
  | { kind: 'organization'; orgId: string }
  | { kind: 'workspace'; workspaceId: string };

/** Settings (what is set, at every level) or the Console (what is watched). */
export type SettingsArea = 'settings' | 'console';

const PREFIX = 'nexus-settings-return-path';

function isAreaPath(area: SettingsArea, path: string): boolean {
  if (!path.startsWith('/') || path.startsWith('//')) return false;
  if (area === 'console') return path.startsWith('/settings/');
  return settingsScopeFromPathname(path) !== null;
}

export function rememberSettingsPath(area: SettingsArea, path: string): void {
  if (!isAreaPath(area, path)) return;
  try {
    window.sessionStorage.setItem(`${PREFIX}:${area}`, path);
  } catch {
    // Storage blocked.
  }
}

/** The last page visited in ``area``, else ``fallback``. */
export function settingsReturnPath(area: SettingsArea, fallback: string): string {
  try {
    const path = window.sessionStorage.getItem(`${PREFIX}:${area}`);
    if (path && isAreaPath(area, path)) return path;
  } catch {
    // Storage blocked.
  }
  return fallback;
}

/** At sign-out: the next person to sign in on this tab starts from their own landing. */
export function forgetSettingsPaths(): void {
  try {
    for (const area of ['settings', 'console'] satisfies SettingsArea[]) {
      window.sessionStorage.removeItem(`${PREFIX}:${area}`);
    }
  } catch {
    // Storage blocked.
  }
}

const ACCOUNT_PATH = /^\/account(?:\/([^/?#]+))?/;
const ORG_SETTINGS_PATH = /^\/organizations\/([^/]+)\/settings/;
const WORKSPACE_SETTINGS_PATH = /^\/workspace\/([^/]+)\/settings/;

/** Which settings scope ``pathname`` belongs to, if any. */
export function settingsScopeFromPathname(pathname: string | null | undefined): SettingsScopeKey | null {
  if (!pathname) return null;
  if (ACCOUNT_PATH.test(pathname)) return { kind: 'account' };
  if (pathname === '/settings' || pathname.startsWith('/settings/')) return { kind: 'platform' };
  const org = ORG_SETTINGS_PATH.exec(pathname);
  if (org) return { kind: 'organization', orgId: org[1] };
  const ws = WORKSPACE_SETTINGS_PATH.exec(pathname);
  if (ws) return { kind: 'workspace', workspaceId: ws[1] };
  return null;
}

/** Whether ``pathname`` is a workspace's settings page (they leave the workspace's chrome). */
export function isWorkspaceSettingsPath(pathname: string | null | undefined): boolean {
  return !!pathname && WORKSPACE_SETTINGS_PATH.test(pathname);
}
