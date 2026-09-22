/**
 * Column-filter state for the tweet tables, and the published value lists
 * behind the checkbox pickers.
 *
 * Filtering is applied in the browser against the rows the snapshot already
 * carries. The *option lists*, though, come from `search_recents_tweets/
 * facets.json`, which is aggregated over the whole query + window at publish
 * time - so ticking a username offers every author in the window, not only the
 * ones visible in the loaded page.
 */
import { RESULTS } from "@/lib/appConfig";
import { withAccessToken } from "@/lib/routes";
import type {
  FacetEntry,
  FacetValue,
  TableEntry,
  TweetRow,
} from "@/lib/types";

/** Columns whose distinct values are enumerable as checkboxes. */
export const FACET_COLUMNS = ["username", "location", "verified_type"];

export type ColumnFilterState = {
  /** Case-insensitive substring match. */
  contains: string;
  /** Exact values ticked in the checkbox list (OR within a column). */
  values: string[];
};

export type ColumnFilters = Record<string, ColumnFilterState>;

export type ColumnValue = FacetValue;

export function isFilterActive(state?: ColumnFilterState): boolean {
  if (!state) return false;
  return Boolean(state.contains.trim()) || state.values.length > 0;
}

export function activeFilterCount(filters: ColumnFilters): number {
  return Object.values(filters).filter(isFilterActive).length;
}

/** The published option list for one column of a query + scenario. */
export function facetValues(
  facets: FacetEntry[] | undefined,
  querySlug: string,
  scenarioId: string,
  column: string,
): ColumnValue[] {
  const entry = (facets || []).find(
    (f) =>
      f.query_slug === querySlug &&
      f.scenario_id === scenarioId &&
      f.column === column,
  );
  return entry?.values || [];
}

/** True when a row passes every active column filter. */
export function rowMatches(
  row: Record<string, unknown>,
  filters: ColumnFilters,
): boolean {
  return Object.entries(filters).every(([column, state]) => {
    if (!isFilterActive(state)) return true;
    const cell = String(row[column] ?? "");
    const contains = state.contains.trim().toLowerCase();
    if (contains && !cell.toLowerCase().includes(contains)) return false;
    if (state.values.length && !state.values.includes(cell)) return false;
    return true;
  });
}


/* ---- Search Tweets: dataset-backed whole-graph search -------------------- */

/** Hits per page - `results.per_page`, the same as Search Users lists. */
export const TWEET_RESULTS_PAGE_SIZE = RESULTS.perPage;

/** One tweet row from dataset search, normalised for the results list. */
export type TweetHit = {
  /** Numeric id from the status URL; `null` when the row carries no usable one. */
  id: string | null;
  text: string;
  url: string;
  username: string;
  createdAt: string;
  location: string;
  verifiedType: string;
  /** True for a post ingested only as context (quote, reply parent, retweet). */
  referenced: boolean;
  mediaCount: number;
  /** Space-separated media URLs, as published. */
  mediaUrl: string;
  /** Slugs of the followed queries whose published rows carried this post. */
  queries: string[];
};

function cell(row: Record<string, unknown>, key: string): string {
  const value = row[key];
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

const DATASET_POSTS_SEARCH = "/app-html/x/apps/x_proxy/dataset/posts/search.json";

export type TweetSearchPage = {
  count: number;
  page: number;
  perPage: number;
  hits: TweetHit[];
};

function hitFromSearchPost(post: Record<string, unknown>): TweetHit {
  const tweetId = cell(post, "tweet_id");
  const username = cell(post, "username");
  const queries = post.queries;
  return {
    id: tweetId || null,
    text: cell(post, "full_text") || cell(post, "text"),
    url: tweetId && username ? `https://x.com/${username}/status/${tweetId}` : "",
    username,
    createdAt: cell(post, "created_at"),
    location: cell(post, "location"),
    verifiedType: cell(post, "verified_type"),
    referenced:
      Boolean(post.referenced) || cell(post, "kind") === "referenced",
    mediaCount: Number(post.media_count) || 0,
    mediaUrl: "",
    queries: Array.isArray(queries)
      ? queries.filter((value): value is string => typeof value === "string")
      : [],
  };
}

/** Paginated search over the canonical tweet graph (Dataset Service). */
export async function loadTweetSearchPage(
  needle: string,
  page: number,
): Promise<TweetSearchPage> {
  const params = new URLSearchParams({
    q: needle,
    page: String(page),
    per_page: String(TWEET_RESULTS_PAGE_SIZE),
  });
  const response = await fetch(
    withAccessToken(`${DATASET_POSTS_SEARCH}?${params}`),
  );
  if (!response.ok) {
    throw new Error(`dataset/posts/search.json HTTP ${response.status}`);
  }
  const doc = (await response.json()) as {
    count?: number;
    page?: number;
    per_page?: number;
    posts?: Record<string, unknown>[];
  };
  return {
    count: Number(doc.count) || 0,
    page: Number(doc.page) || 0,
    perPage: Number(doc.per_page) || TWEET_RESULTS_PAGE_SIZE,
    hits: (doc.posts || []).map((row) => hitFromSearchPost(row)),
  };
}

/**
 * Every post in the Search page's scoped tables, newest first.
 *
 * Used for `findHit`, the Post page's fallback lookup when a tweet id is not in
 * the direct post/user artifacts.
 */
export function tweetHits(tables: TableEntry[] | undefined): TweetHit[] {
  const byId = new Map<string, TweetHit>();
  const loose: TweetHit[] = [];
  for (const table of tables || []) {
    if (table.id !== "tweets") continue;
    for (const row of table.rows || []) {
      const url = cell(row, "url");
      const media = cell(row, "media_url").trim();
      const id = url.match(/\/status\/(\d+)/)?.[1] || null;
      const slug = table.query_slug;
      const existing = id ? byId.get(id) : undefined;
      if (existing) {
        if (slug && !existing.queries.includes(slug)) existing.queries.push(slug);
        continue;
      }
      const hit: TweetHit = {
        id,
        text: cell(row, "text"),
        url,
        username: cell(row, "username").replace(/^@/, ""),
        createdAt: cell(row, "created_at"),
        location: cell(row, "location"),
        verifiedType: cell(row, "verified_type"),
        referenced: Boolean(row.referenced),
        mediaCount: media ? media.split(/\s+/).filter(Boolean).length : 0,
        mediaUrl: media,
        queries: slug ? [slug] : [],
      };
      if (id) byId.set(id, hit);
      else loose.push(hit);
    }
  }
  const hits = [...byId.values(), ...loose];
  for (const hit of hits) hit.queries.sort();
  hits.sort((a, b) => (a.createdAt < b.createdAt ? 1 : a.createdAt > b.createdAt ? -1 : 0));
  return hits;
}

/**
 * Hits matching ``needle``, best match first.
 *
 * Ranked the way `rankUsers` ranks authors: the bands say *how* a hit answered
 * the needle - its author, then its text, then where its author is - and the
 * rows arrive newest-first, so a stable sort leaves the newest post first
 * inside each band. An empty needle lists everything, newest first.
 */
export function rankTweets(hits: TweetHit[], needle: string): TweetHit[] {
  const q = needle.trim().toLowerCase().replace(/^@/, "");
  if (!q) return hits;

  const scored: { hit: TweetHit; score: number }[] = [];
  for (const hit of hits) {
    const username = hit.username.toLowerCase();
    const text = hit.text.toLowerCase();
    const id = (hit.id || "").toLowerCase();
    let score: number;
    if (id && id === q) score = -1;
    else if (id && id.startsWith(q)) score = 0;
    else if (username === q) score = 1;
    else if (username.startsWith(q)) score = 2;
    else if (new RegExp(`\\b${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(text))
      score = 3;
    else if (username.includes(q)) score = 4;
    else if (text.includes(q)) score = 5;
    else if (hit.location.toLowerCase().includes(q)) score = 6;
    else continue;
    scored.push({ hit, score });
  }
  scored.sort((a, b) => a.score - b.score);
  return scored.map((entry) => entry.hit);
}

export function findHit(
  tables: TableEntry[] | undefined,
  tweetId: string | null,
): TweetHit | null {
  if (!tweetId) return null;
  return tweetHits(tables).find((hit) => hit.id === tweetId) || null;
}

/** A hit as the row shape the post card renders. */
export function hitAsRow(hit: TweetHit): TweetRow {
  return {
    created_at: hit.createdAt,
    text: hit.text,
    url: hit.url,
    username: hit.username,
    location: hit.location,
    verified_type: hit.verifiedType,
    ...(hit.mediaUrl ? { media_url: hit.mediaUrl } : {}),
    ...(hit.referenced ? { referenced: true } : {}),
    ...(hit.queries.length ? { queries: hit.queries } : {}),
  };
}
