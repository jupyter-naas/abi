/**
 * Reader for the published Users dataset under `x/apps/x_proxy/search_users/`.
 *
 * Everything here is a plain GET against object storage - no SPARQL runs at
 * request time. The picker index (`users.json`) carries every author in the
 * tweet graph, so searching "grok" reaches an account with a single post; the
 * selected author's posts live in one shard file (`posts/<shard>.json`) -
 * search matches plus referenced context (quotes / replies / retweets they
 * wrote) - and the index row names the shard so the browser never has to hash
 * anything.
 *
 * Index and shards are fetched once and memoised: both are immutable between
 * publishes, and the index is a few MB.
 */
import { FEED, RESULTS } from "@/lib/appConfig";
import type { TweetRow, UserBundle, UserProfile, UserRow } from "@/lib/types";
import { withAccessToken } from "@/lib/routes";

const BASE = "/app-html/x/apps/x_proxy";

/**
 * Posts the author feed shows per batch - `feed.batch` in `config.yaml`.
 *
 * The whole shard is already in memory, so a batch is a slice, not a fetch: the
 * feed opens with one and grows by one whenever the end comes into view or the
 * button is pressed.
 */
export const USER_FEED_BATCH = FEED.batch;

/** Search results per page - `results.per_page` in `config.yaml`. An empty
 * query lists the busiest first. */
export const USER_RESULTS_PAGE_SIZE = RESULTS.perPage;

/**
 * Must match INDEX_COLUMNS in api/search_users/users.py.
 *
 * ``description`` and ``display_name`` are trailing and optional: a publish
 * older than those columns simply has fewer entries, and the row reads as a
 * bio-less / nameless author.
 */
type IndexRow = [
  string,
  number,
  string,
  string,
  string,
  string,
  string?,
  string?,
];

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

/** Which posts of an author the feed is showing. */
export type FeedTab = "all" | "matched" | "referenced";

export type UserFeed = {
  /** The batch on screen. */
  rows: TweetRow[];
  /** Posts in the selected tab, however many are shown. */
  total: number;
  /** Still to come in this tab. */
  remaining: number;
  profile: UserProfile | null;
  counts: Record<FeedTab, number>;
};

let indexPromise: Promise<UserIndex> | null = null;
const shardPromises = new Map<string, Promise<ShardDoc | null>>();

async function getJson<T>(path: string): Promise<T | null> {
  let res: Response;
  try {
    res = await fetch(withAccessToken(`${BASE}/${path}`), { cache: "no-store" });
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
        const [
          username,
          posts,
          last_post_at,
          location,
          verified_type,
          shard,
          description,
          display_name,
        ] = row;
        users.push({
          username,
          posts,
          last_post_at,
          location,
          verified_type,
          description: description || "",
          display_name: display_name || "",
        });
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

/**
 * Authors matching ``needle``, best match first.
 *
 * The index arrives busiest-first, which is the right answer for an empty box
 * but the wrong one for a search: typing "grok" must not bury @grok under every
 * louder account whose handle merely contains those letters. So matches are
 * ranked by how well the handle *or display name* answers the needle, and only
 * then by how much the author has posted.
 */
export function rankUsers(users: UserRow[], needle: string): UserRow[] {
  const q = needle.trim().toLowerCase().replace(/^@/, "");
  if (!q) return users;

  const scored: { user: UserRow; score: number }[] = [];
  for (const user of users) {
    const username = user.username.toLowerCase();
    const name = (user.display_name || "").toLowerCase();
    let score: number;
    if (username === q) score = 0;
    else if (name === q) score = 1;
    else if (username.startsWith(q)) score = 2;
    else if (name.startsWith(q)) score = 3;
    else if (username.includes(q)) score = 4;
    else if (name.includes(q)) score = 5;
    else if ((user.location || "").toLowerCase().includes(q)) score = 6;
    else continue;
    scored.push({ user, score });
  }
  // The index is already sorted by posts, so a stable sort on the score alone
  // keeps the busiest author first within each band.
  scored.sort((a, b) => a.score - b.score);
  return scored.map((entry) => entry.user);
}

/** Tweet id from an ingested post URL (`https://x.com/{user}/status/{id}`). */
export function tweetIdOf(post: { url?: string }): string | null {
  const match = (post.url || "").match(/\/status\/(\d+)/);
  return match ? match[1] : null;
}

/** DOM id of a post card, so the page can scroll one to the top. */
export function postAnchorId(tweetId: string): string {
  return `post-${tweetId}`;
}

/**
 * Posts of one tab.
 *
 * ``matched`` are the posts that answered a followed query - each names which
 * one - and ``referenced`` are the reply parents, quoted tweets and retweeted
 * originals ingested only to explain a match. The words the tabs wear are in
 * `feed.tabs` in `config.yaml`; these keys are the split the data carries.
 */
export function postsInTab(posts: TweetRow[], tab: FeedTab): TweetRow[] {
  if (tab === "matched") return posts.filter((post) => !post.referenced);
  if (tab === "referenced") {
    return posts.filter((post) => Boolean(post.referenced));
  }
  return posts;
}

/** The post *tweetId* names, from anywhere in the author's history. */
export function findPost(
  bundle: UserBundle | null,
  tweetId: string | null,
): TweetRow | null {
  if (!tweetId) return null;
  return (bundle?.posts || []).find((post) => tweetIdOf(post) === tweetId) || null;
}

/**
 * What the feed renders: the first ``shown`` posts of ``tab``, plus the counts
 * the tabs label themselves with.
 *
 * Everything is a slice of the bundle already in memory, so growing the feed
 * costs nothing but a render.
 */
export function feedOf(
  bundle: UserBundle | null,
  tab: FeedTab,
  shown: number,
): UserFeed {
  const posts = bundle?.posts || [];
  const inTab = postsInTab(posts, tab);
  const matched = posts.filter((post) => !post.referenced).length;
  return {
    rows: inTab.slice(0, Math.max(0, shown)),
    total: inTab.length,
    remaining: Math.max(0, inTab.length - Math.max(0, shown)),
    profile: bundle?.profile || null,
    counts: {
      all: posts.length,
      matched,
      referenced: posts.length - matched,
    },
  };
}
