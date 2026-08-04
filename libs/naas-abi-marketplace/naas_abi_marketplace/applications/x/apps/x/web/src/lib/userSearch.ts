/**
 * Reader for the published Users dataset under `x/apps/x/search_users/`.
 *
 * Everything here is a plain GET against object storage — no SPARQL runs at
 * request time. The picker index (`users.json`) carries every author in the
 * tweet graph, so searching "grok" reaches an account with a single post; the
 * selected author's posts live in one shard file (`posts/<shard>.json`), and
 * the index row names the shard so the browser never has to hash anything.
 *
 * Index and shards are fetched once and memoised: both are immutable between
 * publishes, and the index is a few MB.
 */
import type { TweetRow, UserBundle, UserProfile, UserRow } from "@/lib/types";

const BASE = "/app-html/x/apps/x";

/** Posts per page in the table. Pagination is client-side over the shard. */
export const USER_POSTS_PAGE_SIZE = 100;

/** Must match INDEX_COLUMNS in api/search_users/users.py. */
type IndexRow = [string, number, string, string, string, string];

type IndexDoc = {
  format?: number;
  users?: IndexRow[];
};

type ShardDoc = {
  shard?: string;
  authors?: Record<string, UserBundle>;
};

export type UserIndex = {
  users: UserRow[];
  /** username → shard file holding that author's posts. */
  shardOf: Map<string, string>;
};

export type UserPostsPage = {
  rows: TweetRow[];
  total: number;
  offset: number;
  profile: UserProfile | null;
};

let indexPromise: Promise<UserIndex> | null = null;
const shardPromises = new Map<string, Promise<ShardDoc | null>>();

async function getJson<T>(path: string): Promise<T | null> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/${path}`, { cache: "no-store" });
  } catch {
    return null;
  }
  if (!res.ok) return null;
  try {
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** Every author in the tweet graph, busiest first. Memoised per session. */
export function loadUserIndex(): Promise<UserIndex> {
  if (!indexPromise) {
    indexPromise = getJson<IndexDoc>("search_users/users.json").then((doc) => {
      const users: UserRow[] = [];
      const shardOf = new Map<string, string>();
      for (const row of doc?.users || []) {
        const [username, posts, last_post_at, location, verified_type, shard] =
          row;
        users.push({ username, posts, last_post_at, location, verified_type });
        shardOf.set(username, shard);
      }
      return { users, shardOf };
    });
  }
  return indexPromise;
}

function loadShard(shard: string): Promise<ShardDoc | null> {
  let pending = shardPromises.get(shard);
  if (!pending) {
    pending = getJson<ShardDoc>(`search_users/posts/${shard}.json`);
    shardPromises.set(shard, pending);
  }
  return pending;
}

/**
 * An author's profile and full post list, newest first.
 *
 * Returns `null` when the author is not in the published dataset, which the
 * page renders as "no posts found" rather than as an error.
 */
export async function loadUserBundle(
  username: string,
): Promise<UserBundle | null> {
  const { shardOf } = await loadUserIndex();
  const shard = shardOf.get(username);
  if (!shard) return null;
  const doc = await loadShard(shard);
  const bundle = doc?.authors?.[username];
  if (!bundle) return null;
  return { profile: bundle.profile, posts: bundle.posts || [] };
}

/** One page of an author's posts, sliced from an already-loaded bundle. */
export function pageOf(
  bundle: UserBundle | null,
  offset: number,
): UserPostsPage {
  const posts = bundle?.posts || [];
  const start = Math.max(0, Math.min(offset, posts.length));
  return {
    rows: posts.slice(start, start + USER_POSTS_PAGE_SIZE),
    total: posts.length,
    offset: start,
    profile: bundle?.profile || null,
  };
}
