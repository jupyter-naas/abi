import type { FilesSource } from './drive-label';

/**
 * A navigation into a folder (sidebar tree, starred item, deep link) that the page has
 * not listed yet: the folder of a view that is not the rendered one yet.
 */
export type PendingNavigation = { source: FilesSource; path: string };

/**
 * Starting a navigation: `before` and `after` are the open view before and after
 * `setActiveSource`. Same view: nothing will list it later, so list the folder now.
 * Another view: its source-change run lists the folder.
 */
export function startNavigation(
  before: FilesSource,
  after: FilesSource,
  path: string,
): { listNow: string | null; pending: PendingNavigation | null } {
  if (before === after) return { listNow: path, pending: null };
  return { listNow: null, pending: { source: after, path } };
}

/**
 * What the page lists when the open view changes (`rendered` is this render's view,
 * `current` the store's): the pending navigation's folder once its view is rendered;
 * nothing while the render is behind the store (that navigation's view is coming);
 * else the view's root, dropping a navigation another change overrode.
 */
export function listOnSourceChange(
  pending: PendingNavigation | null,
  rendered: FilesSource,
  current: FilesSource,
): { list: string | null; pending: PendingNavigation | null } {
  if (pending) {
    if (pending.source === rendered) return { list: pending.path, pending: null };
    if (pending.source === current) return { list: null, pending };
  }
  return { list: '', pending: null };
}
