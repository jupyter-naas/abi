/**
 * The last workspace page the user was on, so settings pages (Organization,
 * Platform, Account) can send them straight back there. Per tab (sessionStorage);
 * storage can be blocked, in which case callers use their fallback.
 */
const KEY = 'nexus-workspace-return-path';
const WORKSPACE_PATH = /^\/workspace\/[^/?#]+(?:\/[^?#]*)?(?:[?#].*)?$/;
// A workspace's settings are settings: going back from them never lands on them.
const WORKSPACE_SETTINGS = /^\/workspace\/[^/?#]+\/settings(?:[/?#]|$)/;

function isWorkspacePage(path: string): boolean {
  return WORKSPACE_PATH.test(path) && !WORKSPACE_SETTINGS.test(path);
}

export function rememberWorkspacePath(path: string): void {
  if (!isWorkspacePage(path)) return;
  try {
    window.sessionStorage.setItem(KEY, path);
  } catch {
    // Storage blocked: settings fall back to the workspace chat.
  }
}

/** The remembered page if it belongs to ``workspaceId`` (when given), else ``fallback``. */
export function workspaceReturnPath(fallback: string, workspaceId?: string | null): string {
  try {
    const path = window.sessionStorage.getItem(KEY);
    if (path && isWorkspacePage(path)) {
      if (!workspaceId || path.startsWith(`/workspace/${workspaceId}`)) return path;
    }
  } catch {
    // Storage blocked.
  }
  return fallback;
}
