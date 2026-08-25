"use client";

import { useEffect, useRef, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { KpiGrid } from "@/components/KpiGrid";
import { UserPostCard } from "@/components/UserPostCard";
import { UserProfileCard } from "@/components/UserProfileCard";
import {
  feedOf,
  findPost,
  loadUserBundle,
  postAnchorId,
  USER_FEED_BATCH,
  tweetIdOf,
} from "@/lib/userSearch";
import type { FeedTab } from "@/lib/userSearch";
import type { KpiItem, UserBundle, UserRow } from "@/lib/types";

/** The feed's tabs, in the order they are shown. */
const TABS: { key: FeedTab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "matched", label: "Matched" },
  { key: "context", label: "Context" },
];

type Props = {
  username: string;
  /** The index row for this author, when the search index knows them. */
  known: UserRow | null;
  indexLoading: boolean;
  timezone: string;
  needle: string;
  /** Tweet id aligned to the top of the page, from ``?post=``. */
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

/** Height of the sticky page header, so a scroll target lands under it. */
function headerOffset(): number {
  const head = document.querySelector<HTMLElement>(".main-head");
  return head ? head.getBoundingClientRect().height : 0;
}

/**
 * One author's page: who they are, then what was ingested from them.
 *
 * Opened from a search result and closed back to it. The posts come from the
 * one shard holding this author, so paging is a slice of an array already in
 * memory rather than another fetch. Clicking a post URL or its text scrolls
 * that post to the top of the page and records it in `?post=` — the feed keeps
 * its order, so the post you clicked is the one you end up looking at.
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
  const [tab, setTab] = useState<FeedTab>("all");
  const [shown, setShown] = useState(USER_FEED_BATCH);
  const [loading, setLoading] = useState(true);
  // Sentinel at the end of the feed: once it scrolls into view, the next batch
  // is already rendered by the time the reader gets there.
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setShown(USER_FEED_BATCH);
    setTab("all");
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

  // A new tab starts again at the first batch.
  useEffect(() => {
    setShown(USER_FEED_BATCH);
  }, [tab]);

  // What the feed renders, and the post open on its own page (if any). Both
  // are slices of the bundle already in memory.
  const feed = feedOf(bundle, tab, shown);
  const openPost = findPost(bundle, selectedPost);

  // Growing the feed by scroll. The observer is rebuilt whenever the batch
  // changes, so it always watches the sentinel at the current end.
  useEffect(() => {
    const node = endRef.current;
    if (!node || loading || !feed.remaining) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShown((count) => count + USER_FEED_BATCH);
        }
      },
      // A little early, so the next batch lands before the end is reached.
      { rootMargin: "300px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  });


  // Closing an expanded post comes back to its card in the feed, which is
  // where the reader left off — and a `?post=` deep link may name a post
  // further down than the feed has grown, so make sure it is rendered.
  const closePost = () => {
    const target = selectedPost;
    if (target && bundle) {
      const index = bundle.posts.findIndex(
        (post) => tweetIdOf(post) === target,
      );
      if (index >= 0) {
        setTab("all");
        setShown((count) => Math.max(count, index + 1));
      }
    }
    onSelectPost(null);
    if (!target) return;
    // After the feed has rendered the batch holding it.
    window.requestAnimationFrame(() => {
      const card = document.getElementById(postAnchorId(target));
      if (!card) return;
      const top =
        card.getBoundingClientRect().top + window.scrollY - headerOffset() - 8;
      window.scrollTo({ top: Math.max(0, top) });
    });
  };

  const profile = feed.profile || known;
  const total = feed.counts.all || known?.posts || 0;
  const rows = feed.rows;
  const lastPostAt = profile?.last_post_at || rows[0]?.created_at || "";
  const firstPostAt = feed.profile?.first_post_at || "";
  const pinned = pinnedUsers.includes(username);
  const unknown = !indexLoading && !loading && !profile && !rows.length;
  const referencedCount = feed.counts.context;
  const matchedCount = feed.counts.matched;
  const postsLoaded = Boolean(bundle) && !loading;

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

  const openPostId = openPost ? tweetIdOf(openPost) : null;

  // One post, alone on the page. Everything else — the profile, the KPIs, the
  // feed — steps aside; ✕ or the back link brings them back.
  if (openPost) {
    return (
      <div className="detail">
        <div className="detail-head">
          <button type="button" className="detail-back" onClick={closePost}>
            ◂ Back to @{username}
          </button>
          <div className="detail-actions">
            <button
              type="button"
              className="detail-close"
              onClick={closePost}
              title="Close this post"
              aria-label="Close this post"
            >
              ✕
            </button>
          </div>
        </div>
        <UserPostCard
          post={openPost}
          username={username}
          needle={needle}
          timezone={timezone}
          selected
          expanded
          onSelect={() => {}}
        />
      </div>
    );
  }

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

      {loading ? <p className="user-empty">Loading posts…</p> : null}
      {!loading && !total ? (
        <p className="user-empty">No post found for this user.</p>
      ) : null}

      {/* The split the "Posts retrieved" KPI names, as tabs over the feed. */}
      {postsLoaded && total ? (
        <div className="feed-tabs" role="tablist" aria-label="Posts">
          {TABS.map((entry) => (
            <button
              key={entry.key}
              type="button"
              role="tab"
              aria-selected={tab === entry.key}
              className={`feed-tab${tab === entry.key ? " active" : ""}`}
              onClick={() => setTab(entry.key)}
            >
              {entry.label}
              <span className="feed-tab-count">{feed.counts[entry.key]}</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="user-posts">
        {rows.map((post) => {
          const id = tweetIdOf(post);
          return (
            <UserPostCard
              key={id || post.url || post.created_at}
              post={post}
              username={username}
              needle={needle}
              timezone={timezone}
              selected={Boolean(id) && id === openPostId}
              onSelect={onSelectPost}
            />
          );
        })}
      </div>

      {postsLoaded && !rows.length && total ? (
        <p className="user-empty">No post in this tab.</p>
      ) : null}

      {/* The sentinel that grows the feed on scroll, and the button for anyone
          who would rather ask than scroll. */}
      {feed.remaining ? (
        <div className="feed-more" ref={endRef}>
          <button
            type="button"
            className="feed-more-btn"
            onClick={() => setShown((count) => count + USER_FEED_BATCH)}
          >
            Show {Math.min(USER_FEED_BATCH, feed.remaining)} more
          </button>
          <span className="feed-more-label">
            {rows.length} of {feed.total} shown
          </span>
        </div>
      ) : rows.length > USER_FEED_BATCH ? (
        <p className="feed-end">All {feed.total} posts shown.</p>
      ) : null}
    </div>
  );
}
