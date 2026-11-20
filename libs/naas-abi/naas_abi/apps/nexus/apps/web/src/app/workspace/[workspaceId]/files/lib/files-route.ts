/**
 * The files URL drives the mobile list-then-detail shell.
 *
 *   /workspace/{id}/files         → drive list (mobile) / browser (desktop)
 *   /workspace/{id}/files/browse → file browser (mobile detail)
 *
 * Query params stay inside the authenticated Files UI. Storage keys are not
 * HTTP routes:
 *
 *   ?source=platform-files&path=shared/docs/deck.pptx
 *
 * The page keeps its state in the URL (`filesStateFromUrl`, `filesUrlQuery`):
 *
 *   ?drive=all&view=all&source=workspace-files&path=finance/q3
 *
 * `drive` is the Drive picker, `view` the View picker, `source` the open view and
 * `path` its folder. A bare /files opens the default (All Views / Workspace Files).
 *
 * `source` is a view (`my-files`, `workspace-files`, `organization-files`,
 * `platform-files`, `system-files`) or `all`; the old drive sources (`my-drive`,
 * `workspace`, `organization-drive`, `platform-drive`, `system-drive`) still open
 * the view they became.
 */

import {
  ALL_VIEWS,
  FILES_ENTRY,
  filesDriveFrom,
  filesSourceFrom,
  type FilesDrive,
  type FilesSource,
} from './drive-label';

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

/** Strip storage-root prefixes so Files can fetch a view-relative path. */
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
  source: FilesSource | null;
  path: string | null;
}

/** Read `?source=&path=` from a Files URL (view + path inside that view). */
export function parseFilesDeepLink(search: string | null | undefined): FilesDeepLink {
  if (!search) return { source: null, path: null };
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const source = filesSourceFrom(params.get('source'));
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
 * `previewPath` stays view-relative; the browse page matches listed FileInfo paths.
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

/** Find a listed row for a view-relative or storage-root preview path. */
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

/** The Files page's state, as its URL holds it. */
export interface FilesUrlState {
  drive: FilesDrive;
  /** The View picker: All Views or one view. */
  view: FilesSource;
  /** The open view (All Views' root: `all`). */
  source: FilesSource;
  /** The open folder ('' for the view's root). */
  path: string;
}

const FILES_URL_KEYS = ['drive', 'view', 'source', 'path'] as const;

/**
 * The state a Files URL opens. A URL naming none of `drive`, `view`, `source`, `path`
 * opens the default (All Drives, "All Views / Workspace Files"); an old `?source=&path=`
 * link opens its view inside All Views; unknown values read as the defaults.
 */
export function filesStateFromUrl(search: string | null | undefined): FilesUrlState {
  const params = new URLSearchParams((search ?? '').replace(/^\?/, ''));
  if (!FILES_URL_KEYS.some((key) => params.has(key))) {
    return { drive: 'all', view: FILES_ENTRY.view, source: FILES_ENTRY.source, path: '' };
  }
  const drive = filesDriveFrom(params.get('drive') ?? 'all');
  const view = filesSourceFrom(params.get('view')) ?? ALL_VIEWS;
  const source = filesSourceFrom(params.get('source')) ?? (view !== ALL_VIEWS ? view : ALL_VIEWS);
  const rawPath = (params.get('path') ?? '').trim();
  return { drive, view, source, path: rawPath ? stripPlatformDrivePrefix(rawPath) : '' };
}

/** The query string of a Files page state (`source` left out at All Views' root, `path` at a view's root). */
export function filesUrlQuery(state: FilesUrlState): string {
  const params = new URLSearchParams();
  params.set('drive', state.drive);
  params.set('view', state.view);
  if (state.source !== ALL_VIEWS) params.set('source', state.source);
  if (state.path) params.set('path', state.path);
  return params.toString();
}

/** The parameters that say what the page opens: its state and a file to preview. */
const FILES_NAVIGATION_KEYS = [...FILES_URL_KEYS, 'preview'] as const;

/**
 * `search` with the Files keys set to `state` (and dropped where `filesUrlQuery` drops
 * them), the preview dropped (the page writes the folder it shows), other parameters kept.
 */
export function filesUrlSearch(search: string, state: FilesUrlState): string {
  const params = new URLSearchParams(search.replace(/^\?/, ''));
  for (const key of FILES_NAVIGATION_KEYS) params.delete(key);
  for (const [key, value] of new URLSearchParams(filesUrlQuery(state))) params.set(key, value);
  const query = params.toString();
  return query ? `?${query}` : '';
}

/**
 * Where a Files URL leads: its state, the folder to list and the file to preview. A URL
 * the page wrote (with `view` or `drive`) names folders in `path` (a dot in a folder name
 * is no file extension) and a file to preview in `preview`; an old `?source=&path=` link
 * whose path looks like a file still opens its folder and previews it.
 */
export function filesNavigationFromUrl(search: string | null | undefined): {
  state: FilesUrlState;
  folderPath: string;
  previewPath: string | null;
} {
  const params = new URLSearchParams((search ?? '').replace(/^\?/, ''));
  const state = filesStateFromUrl(search);
  if (params.has('view') || params.has('drive')) {
    const preview = (params.get('preview') ?? '').trim();
    return { state, folderPath: state.path, previewPath: preview ? stripPlatformDrivePrefix(preview) : null };
  }
  const { folderPath, previewPath } = filesDeepLinkFolderAndPreview(state.path);
  return { state, folderPath, previewPath: previewPath ?? null };
}

/**
 * What a Files URL opens, as a comparable string: its Files keys and preview in one order,
 * other parameters (`spacing`) left out. Two URLs with the same key open the same place.
 */
export function filesUrlKey(search: string): string {
  const params = new URLSearchParams(search.replace(/^\?/, ''));
  const kept = new URLSearchParams();
  for (const key of FILES_NAVIGATION_KEYS) {
    const value = params.get(key);
    if (value !== null) kept.set(key, value);
  }
  return kept.toString();
}

/**
 * The Files query a navigation into `to` (sidebar tree, starred item, search, Home) opens,
 * from the current drive and View picker. As `setActiveSource`: under All Views a view
 * opens inside it, with one view chosen the view becomes the choice.
 */
export function filesNavigationQuery(
  current: { activeDrive: FilesDrive; viewChoice: FilesSource },
  to: { source: string; path: string },
): string {
  const source = filesSourceFrom(to.source) ?? ALL_VIEWS;
  const view = current.viewChoice === ALL_VIEWS || source === ALL_VIEWS ? ALL_VIEWS : source;
  const path = (to.path || '').replace(/^\/+|\/+$/g, '');
  return filesUrlQuery({ drive: current.activeDrive, view, source, path });
}
