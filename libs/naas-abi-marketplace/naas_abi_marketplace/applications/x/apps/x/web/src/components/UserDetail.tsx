"use client";

import { useEffect, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { KpiGrid } from "@/components/KpiGrid";
import { UserPostCard } from "@/components/UserPostCard";
import { UserProfileCard } from "@/components/UserProfileCard";
import {
  loadUserBundle,
  pageOf,
  tweetIdOf,
  USER_POSTS_PAGE_SIZE,
} from "@/lib/userSearch";
import type { KpiItem, UserBundle, UserRow } from "@/lib/types";

type Props = {
  username: string;
  /** The index row for this author, when the search index knows them. */
  known: UserRow | null;
  indexLoading: boolean;
  timezone: string;
  needle: string;
  /** Tweet id pinned to the top of the page, from ``?post=``. */
  selectedPost: string | null;
  onSelectPost: (tweetId: string | null) => void;
  /** Closes the page and returns to the search results it was opened from. */
  onClose: () => void;
};

function formatInstant(iso: string, timezone: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      timeZone: timezone,
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatAgo(iso: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

/**
 * One author's page: who they are, then what was ingested from them.
 *
 * Opened from a search result and closed back to it. The posts come from the
 * one shard holding this author, so paging is a slice of an array already in
 * memory rather than another fetch. Clicking a post URL pins it to the top
 * (`?post=`).
 */
export function UserDetail({
  username,
  known,
  indexLoading,
  timezone,
  needle,
  selectedPost,
  onSelectPost,
  onClose,
}: Props) {
  const { pinnedUsers, togglePinnedUser } = useAppState();
  const [bundle, setBundle] = useState<UserBundle | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setOffset(0);
    loadUserBundle(username)
      .then((res) => {
        if (live) setBundle(res);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [username]);

  useEffect(() => {
    if (selectedPost) window.scrollTo({ top: 0, behavior: "smooth" });
  }, [selectedPost]);

  const page = pageOf(bundle, offset);
  const profile = page.profile || known;
  const total = page.total || known?.posts || 0;
  const rows = page.rows;
  const lastPostAt = profile?.last_post_at || rows[0]?.created_at || "";
  const firstPostAt = page.profile?.first_post_at || "";
  const pinned = pinnedUsers.includes(username);
  const unknown = !indexLoading && !loading && !profile && !rows.length;
  const allPosts = bundle?.posts || [];
  const referencedCount = allPosts.filter((p) => p.referenced).length;
  const matchedCount = allPosts.length
    ? allPosts.length - referencedCount
    : 0;
  const postsLoaded = Boolean(bundle) && !loading;

  const featured = selectedPost
    ? allPosts.find((p) => tweetIdOf(p) === selectedPost) || null
    : null;
  const listed = featured
    ? rows.filter((p) => tweetIdOf(p) !== selectedPost)
    : rows;

  const kpis: KpiItem[] = [
    {
      id: "posts_retrieved",
      label: "Posts retrieved",
      value: total,
      matched: matchedCount,
      referenced: referencedCount,
      hint: postsLoaded
        ? `${matchedCount} matched · ${referencedCount} quoted/replied-to context`
        : "search matches and quoted/replied-to context",
    },
    {
      id: "last_post",
      label: "Last post published",
      value: null,
      text: lastPostAt ? formatInstant(lastPostAt, timezone) : "—",
      hint: lastPostAt ? formatAgo(lastPostAt) : "no post found",
    },
    {
      id: "first_post",
      label: "First post retrieved",
      value: null,
      text: firstPostAt ? formatInstant(firstPostAt, timezone) : "—",
      hint: firstPostAt ? formatAgo(firstPostAt) : "",
    },
  ];

  const pageEnd = offset + rows.length;

  const togglePost = (tweetId: string) => {
    onSelectPost(tweetId === selectedPost ? null : tweetId);
  };

  return (
    <div className="detail">
      <div className="detail-head">
        <button type="button" className="detail-back" onClick={onClose}>
          ◂ Back to search
        </button>
        <div className="detail-actions">
          <button
            type="button"
            className={`pin-toggle${pinned ? " pinned" : ""}`}
            onClick={() => togglePinnedUser(username)}
            title={pinned ? "Unpin from the sidebar" : "Pin to the sidebar"}
            aria-pressed={pinned}
          >
            {pinned ? "★ Pinned" : "☆ Pin"}
          </button>
          <button
            type="button"
            className="detail-close"
            onClick={onClose}
            title="Close this author"
            aria-label="Close this author"
          >
            ✕
          </button>
        </div>
      </div>

      {unknown ? (
        <p className="user-empty">
          @{username} is not in the published X graph — check the handle in the
          URL.
        </p>
      ) : (
        <UserProfileCard
          profile={profile}
          username={username}
          timezone={timezone}
        />
      )}

      <KpiGrid items={kpis} columns={3} accentFirst />

      {featured ? (
        <UserPostCard
          post={featured}
          username={username}
          needle={needle}
          timezone={timezone}
          selected
          onSelect={togglePost}
        />
      ) : null}

      {loading ? <p className="user-empty">Loading posts…</p> : null}
      {!loading && !total ? (
        <p className="user-empty">No post found for this user.</p>
      ) : null}

      {listed.map((post) => (
        <UserPostCard
          key={tweetIdOf(post) || post.url || post.created_at}
          post={post}
          username={username}
          needle={needle}
          timezone={timezone}
          selected={false}
          onSelect={togglePost}
        />
      ))}

      {total > USER_POSTS_PAGE_SIZE ? (
        <div className="pager">
          <button
            type="button"
            className="pager-btn"
            disabled={offset === 0 || loading}
            onClick={() =>
              setOffset((o) => Math.max(0, o - USER_POSTS_PAGE_SIZE))
            }
          >
            ◂ Previous
          </button>
          <span className="pager-label">
            Page {Math.floor(offset / USER_POSTS_PAGE_SIZE) + 1} of{" "}
            {Math.max(1, Math.ceil(total / USER_POSTS_PAGE_SIZE))}
          </span>
          <button
            type="button"
            className="pager-btn"
            disabled={pageEnd >= total || loading}
            onClick={() => setOffset((o) => o + USER_POSTS_PAGE_SIZE)}
          >
            Next ▸
          </button>
        </div>
      ) : null}
    </div>
  );
}
