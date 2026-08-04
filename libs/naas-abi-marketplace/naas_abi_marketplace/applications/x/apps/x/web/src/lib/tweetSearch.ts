/**
 * Client for the live tweet-search routes behind the Search page table.
 *
 * The published snapshot only carries the newest N tweets per query + window,
 * so filtering it client-side can only ever narrow that page. These endpoints
 * re-query the graph instead, returning the newest N tweets that actually
 * match. When the routes are unavailable (a purely static copy of the export
 * with no ABI backend), every call resolves to `null` and the table falls back
 * to filtering the snapshot rows it already has.
 */
import type { TweetRow } from "@/lib/types";

const BASE = "/app-html/x/apps/x";

/** Columns whose distinct values are enumerable as checkboxes. */
export const FACET_COLUMNS = ["username", "location", "verified_type"];

export type ColumnFilterState = {
  /** Case-insensitive substring match. */
  contains: string;
  /** Exact values ticked in the checkbox list (OR within a column). */
  values: string[];
};

export type ColumnFilters = Record<string, ColumnFilterState>;

export type TweetSearchContext = {
  query: string;
  startTime: string;
  endTime: string;
  limit: number;
};

export type ColumnValue = {
  value: string;
  count: number;
};

export function isFilterActive(state?: ColumnFilterState): boolean {
  if (!state) return false;
  return Boolean(state.contains.trim()) || state.values.length > 0;
}

export function activeFilterCount(filters: ColumnFilters): number {
  return Object.values(filters).filter(isFilterActive).length;
}

/** Drop empty entries so the serialized payload stays minimal. */
function prune(filters: ColumnFilters): ColumnFilters {
  const out: ColumnFilters = {};
  for (const [column, state] of Object.entries(filters)) {
    if (isFilterActive(state)) out[column] = state;
  }
  return out;
}

function params(
  ctx: TweetSearchContext,
  filters: ColumnFilters,
): URLSearchParams {
  const search = new URLSearchParams({
    query: ctx.query,
    start_time: ctx.startTime,
    end_time: ctx.endTime,
  });
  const pruned = prune(filters);
  if (Object.keys(pruned).length) {
    search.set("filters", JSON.stringify(pruned));
  }
  return search;
}

async function getJson<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T | null> {
  let res: Response;
  try {
    res = await fetch(path, { cache: "no-store", signal });
  } catch (err) {
    // AbortError is a superseded keystroke, not a missing backend — rethrow so
    // the caller can ignore it without flipping into offline fallback mode.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    return null;
  }
  if (!res.ok) return null;
  try {
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function fetchTweets(
  ctx: TweetSearchContext,
  filters: ColumnFilters,
  signal?: AbortSignal,
): Promise<{ rows: TweetRow[]; truncated: boolean } | null> {
  const search = params(ctx, filters);
  search.set("limit", String(ctx.limit));
  const body = await getJson<{
    rows?: TweetRow[];
    truncated?: boolean;
  }>(`${BASE}/api/tweets?${search.toString()}`, signal);
  if (!body) return null;
  return { rows: body.rows || [], truncated: Boolean(body.truncated) };
}

export async function fetchColumnValues(
  ctx: TweetSearchContext,
  column: string,
  contains: string,
  filters: ColumnFilters,
  signal?: AbortSignal,
): Promise<{ values: ColumnValue[]; truncated: boolean } | null> {
  const search = params(ctx, filters);
  search.set("column", column);
  if (contains.trim()) search.set("contains", contains.trim());
  const body = await getJson<{
    values?: ColumnValue[];
    truncated?: boolean;
  }>(`${BASE}/api/tweets/values?${search.toString()}`, signal);
  if (!body) return null;
  return { values: body.values || [], truncated: Boolean(body.truncated) };
}
