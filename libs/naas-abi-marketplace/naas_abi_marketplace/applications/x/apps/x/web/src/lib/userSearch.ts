/**
 * Client for the graph-wide author routes behind the Users page.
 *
 * These take no query or window: searching "grok" reaches every author in the
 * tweet graph, and a selected author's posts are paged through with
 * limit/offset. When the routes are unavailable (a static copy of the export
 * with no ABI backend) every call resolves to `null` and the page falls back
 * to the published `search_users/users.json` list.
 */
import type { TweetRow, UserAccount, UserRow } from "@/lib/types";

const BASE = "/app-html/x/apps/x";

/** Posts per page — matches DEFAULT_USER_POSTS_PAGE in routes.py. */
export const USER_POSTS_PAGE_SIZE = 100;

export type UserPostsPage = {
  rows: TweetRow[];
  total: number;
  offset: number;
  profile: UserRow & UserAccount & { first_post_at?: string };
};

async function getJson<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T | null> {
  let res: Response;
  try {
    res = await fetch(path, { cache: "no-store", signal });
  } catch (err) {
    // AbortError is a superseded request, not a missing backend.
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

export async function searchUsers(
  contains: string,
  signal?: AbortSignal,
): Promise<UserRow[] | null> {
  const search = new URLSearchParams();
  if (contains.trim()) search.set("contains", contains.trim());
  const body = await getJson<{ users?: UserRow[] }>(
    `${BASE}/api/users?${search.toString()}`,
    signal,
  );
  if (!body) return null;
  return body.users || [];
}

export async function fetchUserPosts(
  username: string,
  offset: number,
  signal?: AbortSignal,
): Promise<UserPostsPage | null> {
  const search = new URLSearchParams({
    username,
    limit: String(USER_POSTS_PAGE_SIZE),
    offset: String(offset),
  });
  const body = await getJson<{
    rows?: TweetRow[];
    total?: number;
    offset?: number;
    profile?: UserPostsPage["profile"];
  }>(`${BASE}/api/users/posts?${search.toString()}`, signal);
  if (!body) return null;
  return {
    rows: body.rows || [],
    total: body.total || 0,
    offset: body.offset ?? offset,
    profile:
      body.profile ||
      ({
        username,
        posts: 0,
        last_post_at: "",
        location: "",
        verified_type: "",
      } as UserPostsPage["profile"]),
  };
}
