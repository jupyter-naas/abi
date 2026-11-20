import { filesUrlKey } from './files-route';

/**
 * The Files page and its URL, for one page load (kept across mounts: Back from another page
 * to a URL the page wrote re-uses the store as it is). URLs are compared by `filesUrlKey`, so
 * a change of other parameters (`spacing`) is never a navigation.
 */
export interface FilesUrlSync {
  /** What the URL last applied or written opens (null before the page applied one). */
  applied: string | null;
  /** What the URL a navigation pushed (tree, starred item, search, Home) opens, until it lands. */
  expect: string | null;
}

export function createFilesUrlSync(): FilesUrlSync {
  return { applied: null, expect: null };
}

/**
 * A navigation that pushes `url` starts while the URL is `current`. The navigation opens its
 * folder itself, so its URL, once landed, is taken as applied. A navigation that pushes no
 * URL (a move or rename that rewrites the open folder) waits for nothing: the page writes its
 * state once it settles.
 */
export function expectFilesUrl(sync: FilesUrlSync, url: string | undefined, current: string): void {
  if (url === undefined) return;
  const key = filesUrlKey(url);
  if (key === filesUrlKey(current)) {
    sync.applied = key;
    sync.expect = null;
    return;
  }
  sync.expect = key;
}

/**
 * The URL is now `search`: whether the page applies it. Not when it is the URL a navigation
 * pushed (that navigation opened it), nor when the page already applied or wrote it. Any
 * other URL (Back, a link, a bare /files) is applied, and the page stops waiting for a push.
 */
export function takeFilesUrl(sync: FilesUrlSync, search: string): boolean {
  const key = filesUrlKey(search);
  if (sync.expect !== null) {
    const landed = key === sync.expect;
    sync.expect = null;
    if (landed) {
      sync.applied = key;
      return false;
    }
  }
  if (key === sync.applied) return false;
  sync.applied = key;
  return true;
}

/**
 * Whether the page writes `next` (its state as a URL) over `current`. Never before it applied
 * a URL, nor while a router navigation is in flight (`navigating`: writing the URL then would
 * make Next drop that navigation). The write is recorded first, so it never comes back as a
 * URL to apply.
 */
export function filesUrlWrite(
  sync: FilesUrlSync,
  next: string,
  current: string,
  navigating: boolean,
): boolean {
  if (sync.applied === null || navigating) return false;
  const key = filesUrlKey(next);
  sync.applied = key;
  return key !== filesUrlKey(current);
}
