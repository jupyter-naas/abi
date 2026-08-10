/**
 * The app's URLs.
 *
 * Every page is a real path — `/users/search`, `/posts/search-posts-recent` —
 * exported as its own HTML file, so a link opens on that page without the
 * browser having to boot the app first and then move. Only the state that
 * cannot be a path stays in the query string: the selected author, the scenario
 * and the query.
 *
 * Paths here are app-relative; Next prepends `basePath` for `<Link>` hrefs, and
 * the same-page writers below never touch the path, so neither needs to know it.
 */
import type { PageKey } from "@/lib/types";

/** Path of each page, relative to the app root.
 *
 * The Posts paths are named after the X endpoints they visualise —
 * `GET /2/tweets/search/recent` and `GET /2/tweets/counts/recent`. Trailing
 * slash matches `trailingSlash: true`, so a link never bounces through a
 * redirect. */
export const PAGE_PATHS: Record<PageKey, string> = {
  count: "/posts/get-posts-counts-recent/",
  search: "/posts/search-posts-recent/",
  users: "/users/search/",
  parameters: "/parameters/",
};

/** Where `/` sends visitors. */
export const DEFAULT_PAGE: PageKey = "count";

const USER_PARAM = "user";
const NEEDLE_PARAM = "q";
const SCENARIO_PARAM = "scenario";
const QUERY_PARAM = "query";
/** Pre-routing links carried the page in `?page=`; still honoured at `/`. */
const LEGACY_PAGE_PARAM = "page";

/** The query-string state, as carried by a URL. */
export type PageParams = {
  /** Selected author; only meaningful on the Users page. */
  user: string | null;
  /** What the Users search box is looking for; kept so closing an author's
   * page returns to the results it was opened from. */
  q: string | null;
  /** Scenario id and query slug; only meaningful on Count / Search. */
  scenario: string | null;
  query: string | null;
};

export const NO_PARAMS: PageParams = {
  user: null,
  q: null,
  scenario: null,
  query: null,
};

/** Strip the decoration a pasted handle may carry (`@grok`, trailing space). */
export function normalizeHandle(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const handle = raw.trim().replace(/^@+/, "");
  return handle || null;
}

function clean(raw: string | null | undefined): string | null {
  const value = (raw || "").trim();
  return value || null;
}

function parse(search: string): PageParams {
  const params = new URLSearchParams(search);
  return {
    user: normalizeHandle(params.get(USER_PARAM)),
    q: clean(params.get(NEEDLE_PARAM)),
    scenario: clean(params.get(SCENARIO_PARAM)),
    query: clean(params.get(QUERY_PARAM)),
  };
}

/** The params in the current URL. */
export function readParams(): PageParams {
  if (typeof window === "undefined") return NO_PARAMS;
  return parse(window.location.search);
}

/** Whether a URL carried any param at all, i.e. is a link into a view. */
export function hasParams(params: PageParams): boolean {
  return Object.values(params).some((value) => value !== null);
}

/**
 * The query string a page publishes.
 *
 * Only the params that page honours are written — the Users page hides the
 * Scenario / Query filters, the other pages have no author — so a shared URL
 * never advertises state the page is not showing.
 */
export function searchFor(page: PageKey, params: Partial<PageParams>): string {
  const search = new URLSearchParams();
  if (page === "users") {
    // The needle comes first: an author's page is a result opened from it.
    if (params.q) search.set(NEEDLE_PARAM, params.q);
    if (params.user) search.set(USER_PARAM, params.user);
  } else if (page === "count" || page === "search") {
    if (params.scenario) search.set(SCENARIO_PARAM, params.scenario);
    if (params.query) search.set(QUERY_PARAM, params.query);
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

/** A shareable href for one page, for `<Link>`. */
export function hrefFor(page: PageKey, params: Partial<PageParams>): string {
  return `${PAGE_PATHS[page]}${searchFor(page, params)}`;
}

/**
 * Rewrite the query string of the page already on screen.
 *
 * The path is left exactly as it is, so this never crosses a route — Next stays
 * on the component it rendered, and only the params change. The existing
 * `history.state` is carried over: it holds the router's own tree, and dropping
 * it would make the next Back a full page load.
 *
 * ``push`` is for navigation Back should undo (picking an author); ``replace``
 * is for refining the page in place (the filters) and for normalising a pasted
 * URL on arrival.
 */
export function writeParams(
  page: PageKey,
  params: Partial<PageParams>,
  mode: "push" | "replace" = "push",
): void {
  if (typeof window === "undefined") return;
  const { pathname, hash, search } = window.location;
  const next = `${pathname}${searchFor(page, params)}${hash}`;
  if (next === `${pathname}${search}${hash}`) return;
  const state = window.history.state;
  if (mode === "push") {
    window.history.pushState(state, "", next);
  } else {
    window.history.replaceState(state, "", next);
  }
}

/** Run ``onChange`` whenever Back / Forward changes the URL. */
export function subscribeToParams(
  onChange: (params: PageParams) => void,
): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => onChange(readParams());
  window.addEventListener("popstate", handler);
  return () => window.removeEventListener("popstate", handler);
}

/**
 * Where a hit on `/` should land.
 *
 * Links minted before the pages had paths carried the whole view in the query
 * string (`?page=users&user=grok`, or just `?user=grok`). They still resolve:
 * the root page reads them once and forwards to the matching path.
 */
export function landingHref(search: string): string {
  const params = parse(search);
  const wanted = clean(new URLSearchParams(search).get(LEGACY_PAGE_PARAM));
  const page = (Object.keys(PAGE_PATHS) as PageKey[]).find(
    (key) => key === wanted,
  );
  return hrefFor(page || (params.user ? "users" : DEFAULT_PAGE), params);
}
