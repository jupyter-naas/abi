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


/* ---- Search Tweets: the published rows as search hits --------------------
 *
 * The Search Tweets page is not scoped by the Scenario / Query filters: it
 * searches every post in the tweet graph, published under `search_tweets/` by
 * `api/search_tweets/posts.py` (see that module's docstring). Not the same
 * dataset as the Search page's `search_recents_tweets/tables.json`, which is
 * capped to the newest rows per configured query + time window.
 */

/** Hits per page - `results.per_page`, the same as Search Users lists. */
export const TWEET_RESULTS_PAGE_SIZE = RESULTS.perPage;

/** One published tweet row, normalised out of the table's loose cells. */
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

const SEARCH_TWEETS_BASE = "/app-html/x/apps/x_proxy/search_tweets";

/**
 * One compact row of `search_tweets/posts.json` / `posts_preview.json`.
 *
 * Must match `INDEX_COLUMNS` in `api/search_tweets/posts.py`: tweet_id,
 * created_at, text, username, location, verified_type, referenced (0/1),
 * media_count, queries (space-separated slugs). No `url` / media URLs - the
 * whole-graph index keeps only what the results list renders.
 */
type PostIndexRow = [
  string,
  string,
  string,
  string,
  string,
  string,
  number,
  number,
  string,
];

type PostIndexDoc = {
  format?: number;
  count?: number;
  posts?: PostIndexRow[];
};

function hitFromIndexRow(row: PostIndexRow): TweetHit {
  const [
    tweetId,
    createdAt,
    text,
    username,
    location,
    verifiedType,
    referenced,
    mediaCount,
    queries,
  ] = row;
  return {
    id: tweetId || null,
    text,
    url: tweetId && username ? `https://x.com/${username}/status/${tweetId}` : "",
    username,
    createdAt,
    location,
    verifiedType,
    referenced: Boolean(referenced),
    mediaCount: Number(mediaCount) || 0,
    mediaUrl: "",
    queries: queries ? queries.split(/\s+/).filter(Boolean) : [],
  };
}

async function getPostIndex(path: string): Promise<TweetHit[]> {
  const res = await fetch(withAccessToken(`${SEARCH_TWEETS_BASE}/${path}`));
  if (!res.ok) throw new Error(`${path} HTTP ${res.status}`);
  const doc = (await res.json()) as PostIndexDoc;
  return (doc.posts || []).map(hitFromIndexRow);
}

let previewPromise: Promise<TweetHit[]> | null = null;

/**
 * The newest 1 000 published posts, whole graph - fast first paint for the
 * Search Tweets page before a needle is submitted. Memoised per session.
 */
export function loadTweetPreview(): Promise<TweetHit[]> {
  if (!previewPromise) {
    previewPromise = getPostIndex("posts_preview.json").catch(() => []);
  }
  return previewPromise;
}

export type TweetSearchPage = {
  count: number;
  page: number;
  perPage: number;
  hits: TweetHit[];
};

/** Search one server-side projection page without downloading the full index. */
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
    withAccessToken(`${SEARCH_TWEETS_BASE}/query.json?${params}`),
  );
  if (!response.ok) throw new Error(`query.json HTTP ${response.status}`);
  const doc = (await response.json()) as PostIndexDoc & {
    page?: number;
    per_page?: number;
  };
  return {
    count: Number(doc.count) || 0,
    page: Number(doc.page) || 0,
    perPage: Number(doc.per_page) || TWEET_RESULTS_PAGE_SIZE,
    hits: (doc.posts || []).map((row) =>
      Array.isArray(row) ? hitFromIndexRow(row) : hitFromSearchPost(row),
    ),
  };
}

function hitFromSearchPost(post: Record<string, unknown>): TweetHit {
  const tweetId = cell(post, "tweet_id");
  const username = cell(post, "username");
  const queries = post.queries;
  return {
    id: tweetId || null,
    text: cell(post, "text"),
    url: tweetId && username ? `https://x.com/${username}/status/${tweetId}` : "",
    username,
    createdAt: cell(post, "created_at"),
    location: cell(post, "location"),
    verifiedType: cell(post, "verified_type"),
    referenced: Boolean(post.referenced),
    mediaCount: Number(post.media_count) || 0,
    mediaUrl: "",
    queries: Array.isArray(queries)
      ? queries.filter((value): value is string => typeof value === "string")
      : [],
  };
}

/**
 * Every post in the Search page's scoped tables, newest first.
 *
 * Not what the Search Tweets page reads (see `loadTweetPreview` /
 * `loadTweetIndex` above) - this stays for `findHit`, the Post page's
 * fallback lookup when a tweet id is not in the direct post/user artifacts. A
 * post that answered two followed queries, or that falls inside two scenario
 * windows, is published in each of those tables - so hits are keyed by tweet
 * id, the query slugs are unioned onto one hit, and the merged list is sorted
 * by date rather than trusting the per-table publish order.
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
        // Same post under another query or window: keep the hit, add the query.
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
  // Newest first, which is also the tie-break `rankTweets` inherits.
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
    // A word starting with the needle beats it appearing mid-word, so "ai"
    // finds posts about AI before it finds posts that merely contain "said".
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


/**
 * The published post with this tweet id, from any query or window.
 *
 * This is what lets `/posts/post/?post=<id>` stand on its own: the id is enough
 * to find the post *and* its author, so `?user=` is only ever a shortcut that
 * saves reading the tables. A post outside every published window is not here -
 * the author's shard still has it, which is what `?user=` is for.
 */
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
