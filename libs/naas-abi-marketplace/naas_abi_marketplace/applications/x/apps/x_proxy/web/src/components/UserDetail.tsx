"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { KpiGrid } from "@/components/KpiGrid";
import { UserPostCard } from "@/components/UserPostCard";
import { UserProfileCard } from "@/components/UserProfileCard";
import {
  feedOf,
  loadUserBundle,
  USER_FEED_BATCH,
  tweetIdOf,
} from "@/lib/userSearch";
import type { FeedTab } from "@/lib/userSearch";
import { FEED } from "@/lib/appConfig";
import { hrefFor } from "@/lib/routes";
import { userLink } from "@/lib/pins";
import type { KpiItem, UserBundle, UserRow } from "@/lib/types";

/** The feed's tabs, worded by `feed.tabs` in `config.yaml`. */
const TABS = FEED.tabs as { key: FeedTab; label: string }[];

type Props = {
  username: string;
  /** The index row for this author, when the search index knows them. */
  known: UserRow | null;
  indexLoading: boolean;
  timezone: string;
  needle: string;
  /** Tweet id the reader came back from, marked in the feed. */
  selectedPost: string | null;
  /** `?expand=1` - this page with none of the app's chrome around it. */
  expanded: boolean;
  /**
   * Enters or leaves the full view.
   *
   * Needed because the toggle only changes the query string of the page it is
   * on: Next keeps the same component mounted and fires no popstate, so the
   * view would never hear about it.
   */
  onExpandChange: (expanded: boolean) => void;
  /** Closes the page and returns to the search results it was opened from. */
  onClose: () => void;
};

function formatInstant(iso: string, timezone: string): string {
  if (!iso) return "-";
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
 * one shard holding this author, so growing the feed is a slice of an array
 * already in memory rather than another fetch. A post opens on its own page
 * (`/posts/post/?post=…`) - the card links there, this page never swaps itself
 * out for one.
 */
export function UserDetail({
  username,
  known,
  indexLoading,
  timezone,
  needle,
  selectedPost,
  expanded,
  onExpandChange,
  onClose,
}: Props) {
  const { pinnedIds, togglePinned } = useAppState();
  const pin = userLink(username);
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

  // What the feed renders - a slice of the bundle already in memory.
  const feed = feedOf(bundle, tab, shown);

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


  const profile = feed.profile || known;
  const total = feed.counts.all || known?.posts || 0;
  const rows = feed.rows;
  const lastPostAt = profile?.last_post_at || rows[0]?.created_at || "";
  const firstPostAt = feed.profile?.first_post_at || "";
  const pinned = pinnedIds.users.includes(pin.id);
  const unknown = !indexLoading && !loading && !profile && !rows.length;
  const referencedCount = feed.counts.referenced;
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
      text: lastPostAt ? formatInstant(lastPostAt, timezone) : "-",
      hint: lastPostAt ? formatAgo(lastPostAt) : "no post found",
    },
    {
      id: "first_post",
      label: "First post retrieved",
      value: null,
      text: firstPostAt ? formatInstant(firstPostAt, timezone) : "-",
      hint: firstPostAt ? formatAgo(firstPostAt) : "",
    },
  ];

  return (
    <div className="detail">
      <div className="detail-head">
        <button type="button" className="detail-back" onClick={onClose}>
          ◂ Back to search
        </button>
        <div className="detail-actions">
          {/* The author's page on its own - same control, same `expand=1`, as
              a post's page. It is a URL, so it can be linked to directly. */}
          <Link
            className="post-expand"
            href={hrefFor("users", { user: username, expand: !expanded })}
            title={expanded ? "Show the app around it" : "Full view"}
            aria-label={expanded ? "Show the app around it" : "Full view"}
            onClick={(event) => {
              if (
                event.defaultPrevented ||
                event.button !== 0 ||
                event.metaKey ||
                event.ctrlKey ||
                event.shiftKey ||
                event.altKey
              ) {
                return;
              }
              event.preventDefault();
              onExpandChange(!expanded);
            }}
          >
            {expanded ? "⤡" : "⤢"}
          </Link>
          <button
            type="button"
            className={`pin-toggle${pinned ? " pinned" : ""}`}
            onClick={() => togglePinned("users", pin)}
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
          @{username} is not in the published X graph - check the handle in the
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
              selected={Boolean(id) && id === selectedPost}
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
