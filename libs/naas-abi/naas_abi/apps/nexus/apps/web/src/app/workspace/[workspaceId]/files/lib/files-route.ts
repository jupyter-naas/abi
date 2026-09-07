/**
 * The files URL drives the mobile list-then-detail shell.
 *
 *   /workspace/{id}/files         → drive list (mobile) / browser (desktop)
 *   /workspace/{id}/files/browse → file browser (mobile detail)
 *
 * Query params stay inside the authenticated Files UI. Storage keys are not
 * HTTP routes:
 *
 *   ?source=platform-drive&path=shared/docs/deck.pptx
 */

export const FILES_BROWSE_SLUG = 'browse';

export interface FilesRoute {
  /** On a files route at all. */
  isFilesRoute: boolean;
  /** File browser is open (mobile detail). */
  isBrowse: boolean;
}

// Lookahead, not a consumed terminator: same contract as parseChatRoute.
const FILES_SEGMENT = /(?:^|\/)files(?:\/([^/?#]+))?(?=[/?#]|$)/;

export function parseFilesRoute(pathname: string | null | undefined): FilesRoute {
  const match = pathname ? FILES_SEGMENT.exec(pathname) : null;
  if (!match) {
    return { isFilesRoute: false, isBrowse: false };
  }
  const slug = match[1] ?? null;
  return {
    isFilesRoute: true,
    isBrowse: slug === FILES_BROWSE_SLUG,
  };
}

/** Path of the file browser for a workspace (mobile detail). */
export function filesBrowsePath(workspaceId: string | null): string {
  return workspaceId
    ? `/workspace/${workspaceId}/files/${FILES_BROWSE_SLUG}`
    : `/files/${FILES_BROWSE_SLUG}`;
}

/** Browse path plus an optional query string (`source`, `path`, and anything else). */
export function filesBrowseHref(
  workspaceId: string | null,
  search?: string | null,
): string {
  const base = filesBrowsePath(workspaceId);
  if (!search) return base;
  const q = search.startsWith('?') ? search.slice(1) : search;
  return q ? `${base}?${q}` : base;
}

const STORAGE_ROOT_PREFIXES = ['naas_abi/platform-drive/', 'platform-drive/'];

/** Strip storage-root prefixes so Files can fetch a drive-relative path. */
export function stripPlatformDrivePrefix(path: string): string {
  let normalized = path.replace(/^\/+|\/+$/g, '');
  for (const prefix of STORAGE_ROOT_PREFIXES) {
    if (normalized === prefix.slice(0, -1)) return '';
    if (normalized.startsWith(prefix)) {
      normalized = normalized.slice(prefix.length);
    }
  }
  return normalized;
}

export interface FilesDeepLink {
  source: string | null;
  path: string | null;
}

/** Read `?source=&path=` from a Files URL (drive + path inside that drive). */
export function parseFilesDeepLink(search: string | null | undefined): FilesDeepLink {
  if (!search) return { source: null, path: null };
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const source = (params.get('source') ?? '').trim() || null;
  const rawPath = (params.get('path') ?? '').trim();
  const path = rawPath ? stripPlatformDrivePrefix(rawPath) : null;
  return { source, path };
}

export function hasFilesDeepLink(search: string | null | undefined): boolean {
  const { source, path } = parseFilesDeepLink(search);
  return Boolean(source || path);
}

/**
 * Split a deep-link path into the folder to list and an optional file to preview.
 * `previewPath` stays drive-relative; the browse page matches listed FileInfo paths.
 */
export function filesDeepLinkFolderAndPreview(path: string): {
  folderPath: string;
  previewPath?: string;
} {
  const normalized = stripPlatformDrivePrefix(path);
  if (!normalized) return { folderPath: '' };
  const name = normalized.split('/').pop() ?? '';
  const looksLikeFile = /\.[A-Za-z0-9]{1,8}$/.test(name);
  if (!looksLikeFile) return { folderPath: normalized };
  const slash = normalized.lastIndexOf('/');
  return {
    folderPath: slash >= 0 ? normalized.slice(0, slash) : '',
    previewPath: normalized,
  };
}

/** Find a listed row for a drive-relative or storage-root preview path. */
export function matchListedFile<T extends { path: string; name: string }>(
  files: T[],
  previewPath: string,
): T | undefined {
  const normalized = stripPlatformDrivePrefix(previewPath);
  if (!normalized) return undefined;
  const name = normalized.split('/').pop() ?? '';
  return files.find((file) => {
    const listed = stripPlatformDrivePrefix(file.path);
    if (listed === normalized || file.path === previewPath) return true;
    if (file.path.endsWith(`/${normalized}`)) return true;
    return Boolean(name && file.name === name);
  });
}
