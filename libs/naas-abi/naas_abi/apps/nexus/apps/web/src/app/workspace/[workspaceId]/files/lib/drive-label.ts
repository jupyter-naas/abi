import type { SyncedFolder } from '@/stores/files';

export type FilesScope = 'workspace' | 'my_drive' | 'platform_drive' | 'system_drive';

/** Map the active sidebar source to the API scope param. */
export function filesScopeForSource(activeSource: string): FilesScope {
  if (activeSource === 'my-drive') return 'my_drive';
  if (activeSource === 'platform-drive') return 'platform_drive';
  if (activeSource === 'system-drive') return 'system_drive';
  return 'workspace';
}

/** Storage root path under which the user's drive content lives. */
export function driveRootForSource(
  activeSource: string,
  workspaceId: string,
  authUserId?: string,
): string {
  if (activeSource === 'my-drive') {
    return authUserId ? `naas_abi/my-drive/${authUserId}` : '';
  }
  if (activeSource === 'platform-drive') return 'naas_abi/platform-drive';
  if (activeSource === 'system-drive') return '';
  return workspaceId ? `naas_abi/workspace-drive/${workspaceId}` : '';
}

/** User-facing label for the active drive. */
export function driveLabelForSource(
  activeSource: string,
  syncedFolder: SyncedFolder | undefined,
  isLocalFolder: boolean,
): string {
  if (isLocalFolder) return syncedFolder?.name || 'Drive';
  if (activeSource === 'my-drive') return 'My Drive';
  if (activeSource === 'platform-drive') return 'Platform Drive';
  if (activeSource === 'system-drive') return 'System Drive';
  return 'Workspace Drive';
}

function stripRoot(path: string, root: string): string | null {
  const normalized = path.replace(/^\/+|\/+$/g, '');
  if (!root) return null;
  if (normalized === root) return '';
  if (normalized.startsWith(`${root}/`)) return normalized.slice(root.length + 1);
  return null;
}

/**
 * Path relative to the drive root for breadcrumbs.
 * Strips legacy bare-workspace-id roots for backwards compatibility.
 */
export function relativeDrivePath(
  currentPath: string,
  driveRoot: string,
  activeSource: string,
  workspaceId: string,
): string {
  const legacyRoots = activeSource === 'workspace' && workspaceId ? [workspaceId] : [];
  let relativePath = (currentPath || '').replace(/^\/+|\/+$/g, '');
  for (const root of [driveRoot, ...legacyRoots]) {
    const stripped = stripRoot(relativePath, root);
    if (stripped !== null) {
      relativePath = stripped;
      break;
    }
  }
  return relativePath;
}
