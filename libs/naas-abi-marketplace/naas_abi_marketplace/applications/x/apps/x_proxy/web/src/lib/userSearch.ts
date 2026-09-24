/**
 * Users search and author feeds — Dataset Service only (`dataset/users/…`).
 */
import { FEED, RESULTS } from "@/lib/appConfig";
import type { TweetRow, UserBundle, UserProfile, UserRow } from "@/lib/types";
import { withAccessToken } from "@/lib/routes";

const APP_BASE = "/app-html/x/apps/x_proxy";
const DATASET_USERS_SEARCH = `${APP_BASE}/dataset/users/search.json`;

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
  return {
    url: tweetId ? `https://x.com/i/status/${tweetId}` : "",
    created_at: String(row.created_at || ""),
    text: String(row.full_text || row.text || ""),
    username,
    location: String(row.location || ""),
    verified_type: String(row.verified_type || ""),
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
    first_post_at: String(row.first_post_at || ""),
    location: String(row.location || ""),
    verified_type: String(row.verified_type || ""),
    description: String(row.description || ""),
    display_name: String(row.display_name || ""),
  };
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(withAccessToken(`${APP_BASE}/${path}`));
  if (!res.ok) {
    throw new Error(`${path} HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function artifactUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return withAccessToken(`${APP_BASE}/${path.replace(/^\/+/, "")}`);
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
  const res = await fetch(withAccessToken(`${DATASET_USERS_SEARCH}?${params}`));
  if (!res.ok) {
    throw new Error(`dataset/users/search.json HTTP ${res.status}`);
  }
  const doc = (await res.json()) as {
    count?: number;
    page?: number;
    per_page?: number;
    users?: Record<string, unknown>[];
  };
  return {
    count: Number(doc.count) || 0,
    page: Number(doc.page) || 0,
    perPage: Number(doc.per_page) || USER_RESULTS_PAGE_SIZE,
    users: (doc.users || []).map((row) =>
      mapDatasetUser(row as Record<string, unknown>),
    ),
  };
}

function mapDatasetProfile(row: Record<string, unknown>): UserProfile {
  const username = String(row.username || "");
  const matched = Number(row.matched_count || 0);
  const referenced = Number(row.referenced_count || 0);
  return {
    username,
    posts: Number(row.posts || 0) || matched + referenced,
    matched_count: matched,
    referenced_count: referenced,
    last_post_at: String(row.last_post_at || ""),
    first_post_at: String(row.first_post_at || ""),
    location: String(row.location || ""),
    verified_type: String(row.verified_type || ""),
    description: String(row.description || ""),
    display_name: String(row.display_name || ""),
    author_id: String(row.author_id || ""),
    profile_image_url: String(row.profile_image_url || ""),
    profile_banner_url: String(row.profile_banner_url || ""),
  };
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

/** One page of an author's feed (newest first). */
export async function loadUserFeedPage(
  username: string,
  page: number,
  perPage: number = USER_FEED_BATCH,
): Promise<UserBundle | null> {
  const key = username.toLowerCase().replace(/^@/, "");
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
  });
  const doc = await getJson<{
    profile?: Record<string, unknown>;
    posts?: Record<string, unknown>[];
    count?: number;
  }>(`dataset/users/${encodeURIComponent(key)}/posts.json?${params}`).catch(
    () => null,
  );
  if (!doc?.profile) return null;
  const profile = mapDatasetProfile(doc.profile as Record<string, unknown>);
  const posts = (doc.posts || []).map((row) =>
    mapDatasetPost(row as Record<string, unknown>),
  );
  return {
    profile,
    posts,
    postTotal: Number(doc.count) || profile.posts || posts.length,
  };
}

/** @deprecated Prefer {@link loadUserFeedPage} — loads one batch only. */
export async function loadUserBundle(
  username: string,
): Promise<UserBundle | null> {
  return loadUserFeedPage(username, 0, USER_FEED_BATCH);
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

function tabGraphTotal(
  profile: UserProfile | null | undefined,
  tab: FeedTab,
  loaded: TweetRow[],
): number {
  if (tab === "matched") {
    return profile?.matched_count ?? loaded.filter((p) => !p.referenced).length;
  }
  if (tab === "referenced") {
    return (
      profile?.referenced_count ?? loaded.filter((p) => p.referenced).length
    );
  }
  return profile?.posts ?? loaded.length;
}

export function feedOf(
  bundle: UserBundle | null,
  tab: FeedTab,
  shown: number,
): UserFeed {
  const posts = bundle?.posts || [];
  const profile = bundle?.profile || null;
  const inTab = postsInTab(posts, tab);
  const tabTotal = tabGraphTotal(profile, tab, posts);
  const matched =
    profile?.matched_count ??
    posts.filter((post) => !post.referenced).length;
  const referenced =
    profile?.referenced_count ?? posts.length - matched;
  const canRevealLoaded = shown < inTab.length;
  const canFetchMore =
    Boolean(bundle) && posts.length < (bundle?.postTotal ?? posts.length);
  return {
    rows: inTab.slice(0, Math.max(0, shown)),
    total: tabTotal,
    remaining: canRevealLoaded || canFetchMore ? 1 : 0,
    profile,
    counts: {
      all: profile?.posts ?? bundle?.postTotal ?? posts.length,
      matched,
      referenced,
    },
  };
}
