import type { StarredNavigation } from '@/stores/files';

// A drive object path always starts with `naas_abi/<drive-segment>/…`. Map the
// drive segment back to the Files-page source id so we can open the file there.
// (See driveRoot in files/page.tsx.)
export const DRIVE_SEGMENT_TO_SOURCE: Record<string, string> = {
  'platform-drive': 'platform-drive',
  'my-drive': 'my-drive',
  'workspace-drive': 'workspace',
};

// API `scope` param used by the /api/files endpoints, keyed by source id.
// Mirrors filesScope in files/page.tsx.
export type FilesScope = 'workspace' | 'my_drive' | 'platform_drive' | 'system_drive';

export function driveScopeForSource(source: string): FilesScope {
  switch (source) {
    case 'my-drive':
      return 'my_drive';
    case 'platform-drive':
      return 'platform_drive';
    case 'system-drive':
      return 'system_drive';
    default:
      return 'workspace';
  }
}

/**
 * True when `href` is a relative drive object path (e.g.
 * `naas_abi/platform-drive/bob/…/LOreal.pptx`) rather than a real URL.
 *
 * The agent emits these as relative markdown links; the browser would otherwise
 * resolve them against the current `/chat/` URL and land on the chat catch-all
 * route instead of opening the file. Callers use this to intercept them.
 */
export function isDriveObjectPath(href?: string | null): href is string {
  if (!href) return false;
  // Reject anything with a URL scheme (http:, https:, mailto:, …) or protocol-relative.
  if (/^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith('//')) return false;
  return href.replace(/^\/+/, '').startsWith('naas_abi/');
}

export interface DriveObjectRef {
  source: string; // Files-page source id (platform-drive, my-drive, workspace, …)
  scope: FilesScope; // API scope param
  path: string; // full normalized object path (naas_abi/<drive>/…)
  parentPath: string; // parent folder's object path
  name: string; // last path segment
  isFile: boolean; // heuristic: last segment contains a "."
}

/** Parse a drive object path into the pieces the Files API / navigation need. */
export function parseDriveObjectPath(objectPath: string): DriveObjectRef {
  const normalized = objectPath.replace(/^\/+|\/+$/g, '');
  const segments = normalized.split('/');
  const driveSegment = segments[1] ?? '';
  const source = DRIVE_SEGMENT_TO_SOURCE[driveSegment] ?? 'system-drive';

  const name = segments[segments.length - 1] ?? '';
  const isFile = name.includes('.');
  const parentPath = normalized.includes('/')
    ? normalized.slice(0, normalized.lastIndexOf('/'))
    : '';

  return {
    source,
    scope: driveScopeForSource(source),
    path: normalized,
    parentPath,
    name,
    isFile,
  };
}

/**
 * Build the Files-page navigation payload for a drive object path, reusing the
 * same store navigation the sidebar's starred-file click uses. For a file we
 * navigate to its parent folder and open the file's preview; for a folder we
 * navigate into it.
 */
export function driveNavigationFor(objectPath: string): StarredNavigation {
  const { source, path, parentPath, isFile } = parseDriveObjectPath(objectPath);
  return isFile
    ? { source, path: parentPath, previewPath: path }
    : { source, path };
}
