/**
 * The files URL drives the mobile list-then-detail shell.
 *
 *   /workspace/{id}/files         → drive list (mobile) / browser (desktop)
 *   /workspace/{id}/files/browse → file browser (mobile detail)
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
