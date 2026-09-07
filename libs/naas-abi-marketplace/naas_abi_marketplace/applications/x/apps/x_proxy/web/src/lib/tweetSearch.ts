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
 * The Search Tweets page reads the same `tables.json` the Search page's tweet
 * table used to render, but as a list of results rather than a grid of cells:
 * one hit per post, ranked against the needle. Everything is in memory already,
 * so searching is a filter and a sort, never a fetch.
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

/**
 * Every published post, newest first.
 *
 * The Search Tweets page is not scoped by the Scenario / Query filters, so it
 * reads *all* the tweet tables the publish carries. A post that answered two
 * followed queries, or that falls inside two scenario windows, is published in
 * each of those tables - so hits are keyed by tweet id, the query slugs are
 * unioned onto one hit, and the merged list is sorted by date rather than
 * trusting the per-table publish order.
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
    let score: number;
    if (username === q) score = 0;
    else if (username.startsWith(q)) score = 1;
    // A word starting with the needle beats it appearing mid-word, so "ai"
    // finds posts about AI before it finds posts that merely contain "said".
    else if (new RegExp(`\\b${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(text))
      score = 2;
    else if (username.includes(q)) score = 3;
    else if (text.includes(q)) score = 4;
    else if (hit.location.toLowerCase().includes(q)) score = 5;
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
