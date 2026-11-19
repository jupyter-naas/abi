/**
 * Last page visited in each settings scope (sessionStorage), so switching scopes
 * reopens where the caller left off.
 */

export type SettingsScopeKey =
  | { kind: 'account' }
  | { kind: 'platform' }
  | { kind: 'organization'; orgId: string }
  | { kind: 'workspace'; workspaceId: string };

const PREFIX = 'nexus-settings-scope-path';

function storageKey(scope: SettingsScopeKey): string {
  switch (scope.kind) {
    case 'account':
      return `${PREFIX}:account`;
    case 'platform':
      return `${PREFIX}:platform`;
    case 'organization':
      return `${PREFIX}:org:${scope.orgId}`;
    case 'workspace':
      return `${PREFIX}:workspace:${scope.workspaceId}`;
  }
}

function isValidScopePath(scope: SettingsScopeKey, path: string): boolean {
  if (!path.startsWith('/') || path.startsWith('//')) return false;
  switch (scope.kind) {
    case 'account':
      return /^\/account(?:\/|$|\?|#)/.test(path);
    case 'platform':
      return /^\/settings(?:\/|$|\?|#)/.test(path);
    case 'organization':
      return new RegExp(`^/organizations/${escapeRegExp(scope.orgId)}/settings(?:/|$|\\?|#)`).test(
        path
      );
    case 'workspace':
      return new RegExp(`^/workspace/${escapeRegExp(scope.workspaceId)}/settings(?:/|$|\\?|#)`).test(
        path
      );
  }
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function rememberSettingsScopePath(scope: SettingsScopeKey, path: string): void {
  if (!isValidScopePath(scope, path)) return;
  try {
    window.sessionStorage.setItem(storageKey(scope), path);
  } catch {
    // Storage blocked.
  }
}

/** Remembered path for ``scope``, else ``fallback``. */
export function settingsScopeReturnPath(scope: SettingsScopeKey, fallback: string): string {
  try {
    const path = window.sessionStorage.getItem(storageKey(scope));
    if (path && isValidScopePath(scope, path)) return path;
  } catch {
    // Storage blocked.
  }
  return fallback;
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

export function scopeKeysEqual(a: SettingsScopeKey, b: SettingsScopeKey): boolean {
  if (a.kind !== b.kind) return false;
  switch (a.kind) {
    case 'account':
    case 'platform':
      return true;
    case 'organization':
      return a.orgId === (b as { kind: 'organization'; orgId: string }).orgId;
    case 'workspace':
      return a.workspaceId === (b as { kind: 'workspace'; workspaceId: string }).workspaceId;
  }
}