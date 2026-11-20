/**
 * The router navigation in flight, as Next reports its start (`onRouterTransitionStart`
 * in `instrumentation-client.ts`): a link, `router.push`/`replace`, Back/Forward.
 *
 * A page that rewrites its own URL (`history.replaceState`) waits while one is in flight:
 * Next turns such a write into a restore of the current page, which drops the pending
 * navigation (a click on Chat would stay on the page).
 */

let pendingUrl: string | null = null;

const urlKey = (location: { pathname: string; search: string }): string =>
  `${location.pathname}${location.search}`;

/** A navigation to `href` started (resolved against `base`, the current location). */
export function noteRouterNavigation(href: string, base: string = window.location.href): void {
  pendingUrl = urlKey(new URL(href, base));
}

/**
 * Whether a navigation started and has not landed: the location is not yet its URL. It has
 * landed once the location is its URL (Back/Forward: at once).
 */
export function routerNavigationPending(
  location: { pathname: string; search: string } = window.location,
): boolean {
  if (pendingUrl === null) return false;
  if (pendingUrl === urlKey(location)) {
    pendingUrl = null;
    return false;
  }
  return true;
}
