/**
 * The last Settings page visited (sessionStorage), and the last one of each level, so the
 * dock's Settings reopens where the caller left off, and each tab its level.
 */

export type SettingsScopeKey =
  | { kind: 'account' }
  | { kind: 'platform' }
  | { kind: 'organization'; orgId: string }
  | { kind: 'workspace'; workspaceId: string };

/** A level of Settings, one tab each. */
export type SettingsLevelId = SettingsScopeKey['kind'];

const PREFIX = 'nexus-settings-return-path';
const LAST_KEY = `${PREFIX}:settings`;
const LEVELS: readonly SettingsLevelId[] = ['platform', 'organization', 'workspace', 'account'];
// Written while the Console was an area of its own: still cleared at sign-out.
const CONSOLE_KEY = `${PREFIX}:console`;

function levelKey(level: SettingsLevelId): string {
  return `${PREFIX}:level:${level}`;
}

function settingsLevelOfPath(path: string): SettingsLevelId | null {
  if (!path.startsWith('/') || path.startsWith('//')) return null;
  return settingsScopeFromPathname(path)?.kind ?? null;
}

function readPath(key: string): string | null {
  try {
    const path = window.sessionStorage.getItem(key);
    return path && settingsLevelOfPath(path) ? path : null;
  } catch {
    // Storage blocked.
    return null;
  }
}

export function rememberSettingsPath(path: string): void {
  const level = settingsLevelOfPath(path);
  if (!level) return;
  try {
    window.sessionStorage.setItem(LAST_KEY, path);
    window.sessionStorage.setItem(levelKey(level), path);
  } catch {
    // Storage blocked.
  }
}

/** The last Settings page visited, at any level, else ``fallback``. */
export function settingsReturnPath(fallback: string): string {
  return readPath(LAST_KEY) ?? fallback;
}

/** The last page visited at ``level``, or null. */
export function settingsLevelReturnPath(level: SettingsLevelId): string | null {
  const path = readPath(levelKey(level));
  return path && settingsLevelOfPath(path) === level ? path : null;
}

/** At sign-out: the next person to sign in on this tab starts from their own landing. */
export function forgetSettingsPaths(): void {
  try {
    for (const key of [LAST_KEY, CONSOLE_KEY, ...LEVELS.map(levelKey)]) {
      window.sessionStorage.removeItem(key);
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
