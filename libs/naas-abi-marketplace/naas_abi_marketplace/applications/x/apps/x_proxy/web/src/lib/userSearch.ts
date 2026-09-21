/**
 * Dataset-backed Users search and author feeds (`dataset/users/…` APIs).
 */
import { FEED, RESULTS } from "@/lib/appConfig";
import type { TweetRow, UserBundle, UserProfile, UserRow } from "@/lib/types";
import { withAccessToken } from "@/lib/routes";

const BASE = "/app-html/x/apps/x_proxy";

export const USER_FEED_BATCH = FEED.batch;
export const USER_RESULTS_PAGE_SIZE = RESULTS.perPage;

export type UserSearchPage = {
  count: number;
  page: number;
  perPage: number;
  users: UserRow[];
};

/** Which posts of an author the feed is showing. */
export type FeedTab = "all" | "matched" | "referenced";

export type UserFeed = {
  rows: TweetRow[];
  total: number;
  remaining: number;
  profile: UserProfile | null;
  counts: Record<FeedTab, number>;
};

const directPostPromises = new Map<string, Promise<TweetRow | null>>();

function mapDatasetPost(row: Record<string, unknown>): TweetRow {
  const tweetId = String(row.tweet_id || "");
  const username = String(row.username || "");
  const handle = username ? `@${username}` : "";
  return {
    url: tweetId ? `https://x.com/i/status/${tweetId}` : "",
    created_at: String(row.created_at || ""),
    text: String(row.full_text || row.text || ""),
    author: handle,
    username,
    lang: String(row.lang || ""),
    like_count: Number(row.like_count || 0),
    retweet_count: Number(row.retweet_count || 0),
    reply_count: Number(row.reply_count || 0),
    referenced: row.kind === "referenced",
    media_url: String(row.media_urls || ""),
    queries: row.query_slug ? [String(row.query_slug)] : [],
  };
}

function mapDatasetUser(row: Record<string, unknown>): UserRow {
  const username = String(row.username || "");
  return {
    username,
    posts:
      Number(row.matched_count || 0) + Number(row.referenced_count || 0),
    last_post_at: String(row.last_post_at || ""),
    location: String(row.location || ""),
    verified_type: String(row.verified_type || ""),
    description: String(row.description || ""),
    display_name: String(row.display_name || ""),
  };
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(withAccessToken(`${BASE}/${path}`));
  if (!res.ok) {
    throw new Error(`${path} HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function artifactUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return withAccessToken(`${BASE}/${path.replace(/^\/+/, "")}`);
}

export async function loadUserSearchPage(
  needle: string,
  page: number,
): Promise<UserSearchPage> {
  const params = new URLSearchParams({
    q: needle,
    page: String(page),
    per_page: String(USER_RESULTS_PAGE_SIZE),
  });
  const doc = await getJson<{
    count?: number;
    page?: number;
    per_page?: number;
    users?: Record<string, unknown>[];
  }>(`dataset/users/search.json?${params}`);
  return {
    count: Number(doc.count) || 0,
    page: Number(doc.page) || 0,
    perPage: Number(doc.per_page) || USER_RESULTS_PAGE_SIZE,
    users: (doc.users || []).map((row) =>
      mapDatasetUser(row as Record<string, unknown>),
    ),
  };
}

/** Summary row for one author (deep links). */
export async function loadUserSummary(
  username: string,
): Promise<UserRow | null> {
  const handle = username.trim().replace(/^@/, "");
  if (!handle) return null;
  const doc = await loadUserSearchPage(handle, 0);
  return (
    doc.users.find((u) => u.username.toLowerCase() === handle.toLowerCase()) ||
    null
  );
}

export function loadPostArtifact(tweetId: string): Promise<TweetRow | null> {
  let pending = directPostPromises.get(tweetId);
  if (!pending) {
    pending = getJson<{ post?: Record<string, unknown> }>(
      `dataset/posts/${encodeURIComponent(tweetId)}.json`,
    )
      .then((doc) =>
        doc?.post ? mapDatasetPost(doc.post as Record<string, unknown>) : null,
      )
      .catch(() => null);
    directPostPromises.set(tweetId, pending);
  }
  return pending;
}

export async function loadUserBundle(
  username: string,
): Promise<UserBundle | null> {
  const key = username.toLowerCase().replace(/^@/, "");
  const doc = await getJson<{
    profile?: Record<string, unknown>;
    posts?: Record<string, unknown>[];
    count?: number;
  }>(
    `dataset/users/${encodeURIComponent(key)}/posts.json?page=0&per_page=5000`,
  ).catch(() => null);
  if (!doc?.profile) return null;
  const profile = doc.profile as UserProfile;
  const posts = (doc.posts || []).map((row) =>
    mapDatasetPost(row as Record<string, unknown>),
  );
  return { profile, posts };
}

export function tweetIdOf(post: { url?: string }): string | null {
  const match = (post.url || "").match(/\/status\/(\d+)/);
  return match ? match[1] : null;
}

export function postAnchorId(tweetId: string): string {
  return `post-${tweetId}`;
}

export function postsInTab(posts: TweetRow[], tab: FeedTab): TweetRow[] {
  if (tab === "matched") return posts.filter((post) => !post.referenced);
  if (tab === "referenced") {
    return posts.filter((post) => Boolean(post.referenced));
  }
  return posts;
}

export function findPost(
  bundle: UserBundle | null,
  tweetId: string | null,
): TweetRow | null {
  if (!tweetId) return null;
  return (bundle?.posts || []).find((post) => tweetIdOf(post) === tweetId) || null;
}

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
