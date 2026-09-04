/**
 * The app's URLs.
 *
 * Every page is a real path - `/users/search`, `/posts/search-posts-recent` -
 * exported as its own HTML file, so a link opens on that page without the
 * browser having to boot the app first and then move. Only the state that
 * cannot be a path stays in the query string: the selected author, the scenario
 * and the query.
 *
 * Paths here are app-relative; Next prepends `basePath` for `<Link>` hrefs, and
 * the same-page writers below never touch the path, so neither needs to know it.
 */
import { DEFAULT_PAGE, PAGE_PATHS, pageConfig } from "@/lib/appConfig";
import type { PageKey } from "@/lib/types";

/**
 * Paths and the landing page are configured, not written here.
 *
 * The Posts paths are named after the X endpoints they visualise -
 * `GET /2/tweets/search/recent` and `GET /2/tweets/counts/recent`. A trailing
 * slash matches `trailingSlash: true`, so a link never bounces through a
 * redirect; Users is the exception, its URL being ``/users/search?user_id=`` with
 * no slash before the query string. Both facts live in `config.yaml` now, and
 * the writers below read the shape off the configured path.
 */
export { DEFAULT_PAGE, PAGE_PATHS } from "@/lib/appConfig";

const USER_PARAM = "user_id";
const USER_PARAM_LEGACY = "user";
const NEEDLE_PARAM = "q";
const POST_PARAM = "post_id";
const POST_PARAM_LEGACY = "post";
/** Where the reader came from, so a detail page's back link is exact. */
const FROM_PARAM = "from";
/** ``expand=1`` - the post alone, with none of the app's chrome around it. */
const EXPAND_PARAM = "expand";
const TOKEN_PARAM = "token";
const SCENARIO_PARAM = "scenario";
const QUERY_PARAM = "query";
/** Pre-routing links carried the page in `?page=`; still honoured at `/`. */
const LEGACY_PAGE_PARAM = "page";

/** The query-string state, as carried by a URL. */
export type PageParams = {
  /** Selected author: the Users page's subject, and the Post page's shortcut. */
  user: string | null;
  /** What the Users search box is looking for; kept so closing an author's
   * page returns to the results it was opened from. */
  q: string | null;
  /** Tweet id of the post the Post page shows. Required there, ignored elsewhere. */
  post: string | null;
  /** Scenario id and query slug; only meaningful on Count / Search. */
  scenario: string | null;
  query: string | null;
  /**
   * Which page a detail page was opened from - `tweets` or `users`. Only the
   * Post page reads it, to know whether back means the search or the author.
   */
  from: string | null;
  /**
   * ``expand=1``: render the detail full-view, without the rail, the tabs or
   * the title bar - a post's page, or an author's.
   */
  expand: boolean;
};

export const NO_PARAMS: PageParams = {
  user: null,
  q: null,
  post: null,
  scenario: null,
  query: null,
  from: null,
  expand: false,
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
    user: normalizeHandle(
      params.get(USER_PARAM) || params.get(USER_PARAM_LEGACY),
    ),
    q: clean(params.get(NEEDLE_PARAM)),
    post: clean(params.get(POST_PARAM) || params.get(POST_PARAM_LEGACY)),
    scenario: clean(params.get(SCENARIO_PARAM)),
    query: clean(params.get(QUERY_PARAM)),
    from: clean(params.get(FROM_PARAM)),
    // Any truthy spelling reads as on; only "1" is ever written.
    expand: ["1", "true", "yes"].includes(
      (params.get(EXPAND_PARAM) || "").toLowerCase(),
    ),
  };
}

/** ``?token=`` that authorises ``/app-html/`` - must ride on every in-app URL. */
export function readAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return clean(new URLSearchParams(window.location.search).get(TOKEN_PARAM));
}

/** Append the current access token so a fetch is authorised like the page. */
export function withAccessToken(url: string): string {
  const token = readAccessToken();
  if (!token || /(?:\?|&)token=/.test(url)) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
}

function attachAccessToken(search: URLSearchParams): void {
  const token = readAccessToken();
  if (token) search.set(TOKEN_PARAM, token);
}

/** The params in the current URL. */
export function readParams(): PageParams {
  if (typeof window === "undefined") return NO_PARAMS;
  return parse(window.location.search);
}

/** Whether a URL carried any param at all, i.e. is a link into a view. */
export function hasParams(params: PageParams): boolean {
  return Object.values(params).some((value) =>
    typeof value === "boolean" ? value : value !== null,
  );
}

/**
 * The query string a page publishes.
 *
 * Only the params that page honours are written - the Users page hides the
 * Scenario / Query filters, the other pages have no author - so a shared URL
 * never advertises state the page is not showing.
 */
export function searchFor(page: PageKey, params: Partial<PageParams>): string {
  const search = new URLSearchParams();
  const config = pageConfig(page);
  // The needle comes first: what a page opened from a result was searching for
  // is the context of everything else in the URL.
  if (config.searchBox && params.q) search.set(NEEDLE_PARAM, params.q);
  if (page === "users") {
    if (params.user) search.set(USER_PARAM, params.user);
    // An author's page can be read on its own too, without the app around it.
    if (params.user && params.expand) search.set(EXPAND_PARAM, "1");
  } else if (page === "post") {
    // The post is the page. The author only says which shard to read, so a link
    // may carry it or not; `from` (and the needle it was found with) say where
    // back goes.
    if (params.post) search.set(POST_PARAM, params.post);
    if (params.user) search.set(USER_PARAM, params.user);
    if (params.from) search.set(FROM_PARAM, params.from);
    if (params.from === "tweets" && params.q) search.set(NEEDLE_PARAM, params.q);
    if (params.expand) search.set(EXPAND_PARAM, "1");
  }
  if (config.filters) {
    // Only a page showing the Scenario / Query dropdowns advertises them.
    if (params.scenario) search.set(SCENARIO_PARAM, params.scenario);
    if (params.query) search.set(QUERY_PARAM, params.query);
  }
  attachAccessToken(search);
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
 * The path is left exactly as it is, so this never crosses a route - Next stays
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
  // Match the configured shape: a page whose path carries no trailing slash
  // keeps none before the query string (Users is ``/users/search?…``).
  const path = PAGE_PATHS[page].endsWith("/")
    ? pathname
    : pathname.replace(/\/+$/, "");
  const next = `${path}${searchFor(page, params)}${hash}`;
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
  const href = hrefFor(page || (params.user ? "users" : DEFAULT_PAGE), params);
  const token = clean(new URLSearchParams(search).get(TOKEN_PARAM));
  if (token && !/[?&]token=/.test(href)) {
    return `${href}${href.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
  }
  return href;
}
