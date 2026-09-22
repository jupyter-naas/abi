import type { FileInfo } from '@/stores/files';
import { filesScopeForSource } from '@/app/workspace/[workspaceId]/files/lib/drive-label';

/** Shared with the browse pane file list for internal drag-and-drop moves. */
export const NEXUS_FILE_DRAG_MIME = 'application/x-nexus-file';

/** Cache / expand key for one directory under a drive source. */
export function explorerDirKey(source: string, path: string): string {
  return `${source}::${normalizeExplorerPath(path)}`;
}

/** Strip leading/trailing slashes so root is always `''`. */
export function normalizeExplorerPath(path: string): string {
  return (path || '').replace(/^\/+|\/+$/g, '');
}

/** Parent directory of a path; root (`''`) has parent `''`. */
export function explorerParentPath(path: string): string {
  const normalized = normalizeExplorerPath(path);
  if (!normalized) return '';
  const idx = normalized.lastIndexOf('/');
  return idx < 0 ? '' : normalized.slice(0, idx);
}

/**
 * True when dropping `sourcePath` onto `targetFolderPath` is a real move.
 * Rejects self, current parent (no-op), and descendants (would nest under itself).
 */
export function canDropOntoExplorerFolder(
  sourcePath: string,
  targetFolderPath: string,
): boolean {
  const source = normalizeExplorerPath(sourcePath);
  const target = normalizeExplorerPath(targetFolderPath);
  if (!source) return false;
  if (source === target) return false;
  if (target.startsWith(`${source}/`)) return false;
  if (explorerParentPath(source) === target) return false;
  return true;
}

/**
 * Rewrite an open browse path after a folder move, or `null` if unaffected.
 * `docs/a` moved to `other/a` with browse at `docs/a/b` becomes `other/a/b`.
 */
export function explorerPathAfterMove(
  currentPath: string,
  oldPath: string,
  newPath: string,
): string | null {
  const current = normalizeExplorerPath(currentPath);
  const from = normalizeExplorerPath(oldPath);
  const to = normalizeExplorerPath(newPath);
  if (!from) return null;
  if (current === from) return to;
  if (current.startsWith(`${from}/`)) {
    return `${to}${current.slice(from.length)}`;
  }
  return null;
}

/**
 * True when `path` is `ancestor` or a descendant of it.
 * Used after rename/delete to decide if the open browse path is stale.
 */
export function explorerPathEqualsOrUnder(path: string, ancestor: string): boolean {
  const target = normalizeExplorerPath(path);
  const prefix = normalizeExplorerPath(ancestor);
  if (!prefix) return true;
  return target === prefix || target.startsWith(`${prefix}/`);
}

/**
 * Entry names for rename: non-empty after trim, no path separators, not `.` / `..`.
 */
export function isValidExplorerEntryName(name: string): boolean {
  const trimmed = name.trim();
  if (!trimmed) return false;
  if (trimmed === '.' || trimmed === '..') return false;
  if (trimmed.includes('/') || trimmed.includes('\\')) return false;
  return true;
}

/** Parent chain for auto-expanding to the open folder (root excluded). */
export function explorerAncestorPaths(path: string): string[] {
  const normalized = normalizeExplorerPath(path);
  if (!normalized) return [];
  const parts = normalized.split('/');
  const out: string[] = [];
  for (let i = 0; i < parts.length; i += 1) {
    out.push(parts.slice(0, i + 1).join('/'));
  }
  return out;
}

/**
 * Directories to expand so `currentPath` is visible under a drive.
 * Root listing is always `''` (API scopes empty path to the drive root).
 * Ancestors above `driveRoot` are skipped; the leaf itself is not expanded.
 */
export function explorerDirsToOpen(currentPath: string, driveRoot: string): string[] {
  const current = normalizeExplorerPath(currentPath);
  const root = normalizeExplorerPath(driveRoot);
  const dirs = [''];
  if (!current) return dirs;

  for (const ancestor of explorerAncestorPaths(current).slice(0, -1)) {
    if (root) {
      if (ancestor === root) continue;
      if (!ancestor.startsWith(`${root}/`)) continue;
    }
    dirs.push(ancestor);
  }
  return dirs;
}

/** Folders only, name-sorted (case-insensitive). */
export function explorerFolderEntries(files: FileInfo[]): FileInfo[] {
  return files
    .filter((file) => file.type === 'folder')
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
}

/** Folders then files, each group name-sorted (case-insensitive). */
export function explorerEntries(files: FileInfo[]): FileInfo[] {
  return files.slice().sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  });
}

/**
 * True when `currentPath` is this folder (or the drive root when path is empty).
 * Compares normalized storage paths; also accepts a trailing-segment match when
 * the browse pane keeps a longer root prefix than the listed child path.
 */
export function isExplorerPathSelected(
  folderPath: string,
  currentPath: string,
  source: string,
  activeSource: string,
): boolean {
  if (source !== activeSource) return false;
  const folder = normalizeExplorerPath(folderPath);
  const current = normalizeExplorerPath(currentPath);
  if (folder === current) return true;
  if (!folder) return current === '';
  return current === folder || current.endsWith(`/${folder}`);
}

/** Query string for one directory listing (no pagination: one folder at a time). */
export function explorerListQuery(
  path: string,
  source: string,
  workspaceId: string | null,
): string {
  const scope = filesScopeForSource(source);
  const target = normalizeExplorerPath(path);
  const params = new URLSearchParams();
  params.set('path', target);
  params.set('scope', scope);
  if (scope !== 'my_drive' && workspaceId) {
    params.set('workspace_id', workspaceId);
  }
  return params.toString();
}

/** Case-insensitive substring match; empty query matches everything. */
export function matchesExplorerQuery(name: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return name.toLowerCase().includes(q);
}

/**
 * True when any already-loaded entry under `path` matches `query` by name.
 * Does not fetch; walks only entries present in `folderCache`.
 */
export function explorerLoadedSubtreeMatches(
  source: string,
  path: string,
  query: string,
  folderCache: Record<string, FileInfo[]>,
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const cached = folderCache[explorerDirKey(source, path)];
  if (!cached) return false;
  for (const entry of explorerEntries(cached)) {
    if (entry.name.toLowerCase().includes(q)) return true;
    if (
      entry.type === 'folder'
      && explorerLoadedSubtreeMatches(
        source,
        normalizeExplorerPath(entry.path),
        query,
        folderCache,
      )
    ) {
      return true;
    }
  }
  return false;
}

/**
 * Keep folders and files whose name matches, or folders with a matching loaded descendant.
 * Empty / whitespace query returns entries unchanged (folders first, then files).
 */
export function filterExplorerEntriesByQuery(
  children: FileInfo[],
  query: string,
  source: string,
  folderCache: Record<string, FileInfo[]>,
): FileInfo[] {
  const entries = explorerEntries(children);
  const q = query.trim().toLowerCase();
  if (!q) return entries;
  return entries.filter((entry) => {
    if (entry.name.toLowerCase().includes(q)) return true;
    if (entry.type !== 'folder') return false;
    return explorerLoadedSubtreeMatches(
      source,
      normalizeExplorerPath(entry.path),
      query,
      folderCache,
    );
  });
}

/** Drive row stays visible when its label matches or loaded entries under it match. */
export function explorerDriveMatchesQuery(
  label: string,
  source: string,
  query: string,
  folderCache: Record<string, FileInfo[]>,
): boolean {
  if (matchesExplorerQuery(label, query)) return true;
  const q = query.trim();
  if (!q) return true;
  return explorerLoadedSubtreeMatches(source, '', query, folderCache);
}
