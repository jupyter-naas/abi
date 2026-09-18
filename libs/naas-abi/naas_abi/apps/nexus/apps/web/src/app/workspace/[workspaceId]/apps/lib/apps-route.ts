/**
 * Apps URL helpers. The workspace id in the URL is the source of truth.
 * Restoring last-open from the zustand id (which lags a workspace switch)
 * was rewriting /workspace/{valeo}/apps back to the previous workspace.
 */

let skipAppsRestore = false;

/** Call before router.push when switching workspaces so Apps stays on the list. */
export function markAppsSkipRestore(): void {
  skipAppsRestore = true;
}

/** Call when the user picks Apps (or another section) inside a workspace. */
export function clearAppsSkipRestore(): void {
  skipAppsRestore = false;
}

export function shouldSkipAppsRestore(): boolean {
  return skipAppsRestore;
}

/** sessionStorage key holding the last app opened in a workspace. */
export function appsLastOpenKey(workspaceId: string | null | undefined): string | null {
  return workspaceId ? `nexus.apps.last_open.${workspaceId}` : null;
}

/**
 * Drop the remembered app so the section lands on the list.
 *
 * "All apps" has to be able to say no to the restore, or the section is a
 * trap: open an app once and every later visit bounces straight back into
 * it. The embed view's Back arrow already forgets it this way; the sidebar
 * link now does the same, so both exits from an app mean the same thing.
 */
export function forgetAppsLastOpen(workspaceId: string | null | undefined): void {
  const key = appsLastOpenKey(workspaceId);
  if (!key) return;
  try {
    sessionStorage.removeItem(key);
  } catch {
    // sessionStorage unavailable (e.g. private mode restrictions) — ignore
  }
}

export function appsPath(workspaceId: string, open?: string | null): string {
  const base = `/workspace/${workspaceId}/apps`;
  if (!open) return base;
  return `${base}?open=${encodeURIComponent(open)}`;
}

/**
 * Where to send the apps URL to reopen the last app, or null to leave it.
 *
 * Returns null when:
 * - the URL already has ?open=
 * - nothing was saved for this workspace
 * - the store is still on another workspace (switch in flight)
 */
export function nextAppsRestoreUrl(params: {
  urlWorkspaceId: string | null | undefined;
  storeWorkspaceId: string | null | undefined;
  searchOpen: string | null | undefined;
  savedOpen: string | null | undefined;
  skipRestore?: boolean;
}): string | null {
  const { urlWorkspaceId, storeWorkspaceId, searchOpen, savedOpen, skipRestore } = params;
  if (skipRestore) return null;
  if (!urlWorkspaceId || !savedOpen) return null;
  if (searchOpen) return null;
  if (storeWorkspaceId && storeWorkspaceId !== urlWorkspaceId) return null;
  return appsPath(urlWorkspaceId, savedOpen);
}
