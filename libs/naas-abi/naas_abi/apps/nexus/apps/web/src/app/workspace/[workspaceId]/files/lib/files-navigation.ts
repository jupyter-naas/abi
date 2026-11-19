import type { FilesSource } from './drive-label';

/**
 * A navigation into a folder (sidebar tree, starred item, deep link): its view, its
 * folder, and whether the navigation listed the folder itself (its view was already open).
 */
export type PendingNavigation = { source: FilesSource; path: string; listed: boolean };

/**
 * Starting a navigation: `before` and `after` are the open view before and after
 * `setActiveSource`. Same view: list the folder now (no source change will). Either way
 * the navigation is remembered, so the next source-change run (the page's mount run, or
 * the view's change) lists its folder or, when already listed, leaves it.
 */
export function startNavigation(
  before: FilesSource,
  after: FilesSource,
  path: string,
): { listNow: string | null; pending: PendingNavigation } {
  const listed = before === after;
  return { listNow: listed ? path : null, pending: { source: after, path, listed } };
}

/**
 * What the page lists when its source-change effect runs (`rendered` is this render's
 * view, `current` the store's): for the navigation's view, its folder, or nothing if the
 * navigation listed it; nothing while the render is behind the store (the navigation's
 * view is coming); with nothing pending, `fallback` (the view's root, or on the page's
 * mount the folder the store already shows for that view); the root when another change
 * overrode the navigation.
 */
export function listOnSourceChange(
  pending: PendingNavigation | null,
  rendered: FilesSource,
  current: FilesSource,
  fallback = '',
): { list: string | null; pending: PendingNavigation | null } {
  if (!pending) return { list: fallback, pending: null };
  if (pending.source === rendered) return { list: pending.listed ? null : pending.path, pending: null };
  if (pending.source === current) return { list: null, pending };
  return { list: '', pending: null };
}
