"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { KpiGrid } from "@/components/KpiGrid";
import { LoadingScreen } from "@/components/LoadingScreen";
import { UserPostCard } from "@/components/UserPostCard";
import { UserProfileCard } from "@/components/UserProfileCard";
import {
  feedOf,
  loadUserFeedPage,
  postsInTab,
  USER_FEED_BATCH,
  tweetIdOf,
} from "@/lib/userSearch";
import type { FeedTab } from "@/lib/userSearch";
import { FEED } from "@/lib/appConfig";
import { hrefFor } from "@/lib/routes";
import { userLink } from "@/lib/pins";
import type { KpiItem, UserBundle, UserProfile, UserRow } from "@/lib/types";

/** The feed's tabs, worded by `feed.tabs` in `config.yaml`. */
const TABS = FEED.tabs as { key: FeedTab; label: string }[];

type Props = {
  username: string;
  /** Optional row from the search results when the profile was opened from the list. */
  known: UserRow | null;
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

function profileFromKnown(known: UserRow | null): UserProfile | null {
  if (!known) return null;
  return {
    username: known.username,
    posts: known.posts,
    last_post_at: known.last_post_at,
    first_post_at: known.first_post_at,
    location: known.location,
    verified_type: known.verified_type,
    description: known.description,
    display_name: known.display_name,
  };
}

function ingestedPostCount(
  known: UserRow | null,
  profile: UserProfile | null,
  bundleCounts: Record<FeedTab, number>,
): number {
  if (known?.posts != null) return known.posts;
  if (profile?.posts != null) return profile.posts;
  return bundleCounts.all;
}

/**
 * One author's page: who they are, then what was ingested from them.
 *
 * KPIs use the search index (full graph totals) as soon as it is available.
 * The post feed opens with the newest ``USER_FEED_BATCH`` rows and grows only
 * when the reader clicks Load more - not on scroll - so the first paint stays
 * light even when the shard holds a long history.
 */
export function UserDetail({
  username,
  known,
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
  const [bundleLoading, setBundleLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [fetchPage, setFetchPage] = useState(0);

  useEffect(() => {
    let live = true;
    setBundleLoading(true);
    setShown(USER_FEED_BATCH);
    setTab("all");
    setFetchPage(0);
    setBundle(null);
    loadUserFeedPage(username, 0, USER_FEED_BATCH)
      .then((res) => {
        if (live) setBundle(res);
      })
      .finally(() => {
        if (live) setBundleLoading(false);
      });
    return () => {
      live = false;
    };
  }, [username]);

  useEffect(() => {
    setShown(USER_FEED_BATCH);
  }, [tab]);

  const feed = feedOf(bundle, tab, shown);
  const profile = feed.profile || profileFromKnown(known);
  const rows = feed.rows;
  const postsLoaded = Boolean(bundle) && !bundleLoading;
  const ingestedTotal = ingestedPostCount(known, feed.profile, feed.counts);
  const lastPostAt =
    profile?.last_post_at || feed.profile?.last_post_at || rows[0]?.created_at || "";
  const firstPostAt =
    feed.profile?.first_post_at || profile?.first_post_at || known?.first_post_at || "";
  const pinned = pinnedIds.users.includes(pin.id);
  const unknown =
    !bundleLoading && !profile && !rows.length && ingestedTotal === 0;
  const referencedCount = feed.counts.referenced;
  const matchedCount = feed.counts.matched;

  const loadMore = async () => {
    const loaded = bundle?.posts || [];
    const inTab = postsInTab(loaded, tab);
    if (shown < inTab.length) {
      setShown((count) => count + USER_FEED_BATCH);
      return;
    }
    if (!bundle || loaded.length >= bundle.postTotal) return;
    setLoadingMore(true);
    try {
      const nextPage = fetchPage + 1;
      const page = await loadUserFeedPage(username, nextPage, USER_FEED_BATCH);
      if (!page) return;
      setFetchPage(nextPage);
      setBundle((prev) => {
        if (!prev) return page;
        const seen = new Set(prev.posts.map((post) => tweetIdOf(post) || post.url));
        const merged = [...prev.posts];
        for (const post of page.posts) {
          const key = tweetIdOf(post) || post.url;
          if (key && seen.has(key)) continue;
          if (key) seen.add(key);
          merged.push(post);
        }
        return {
          profile: page.profile,
          posts: merged,
          postTotal: page.postTotal,
        };
      });
      setShown((count) => count + USER_FEED_BATCH);
    } finally {
      setLoadingMore(false);
    }
  };

  const kpis: KpiItem[] = [
    {
      id: "posts_ingested",
      label: "Posts ingested",
      value: ingestedTotal,
      matched: postsLoaded ? matchedCount : undefined,
      referenced: postsLoaded ? referencedCount : undefined,
      hint: postsLoaded
        ? `${matchedCount} matched · ${referencedCount} quoted/replied-to context in this feed`
        : "total posts ingested for this author in the graph",
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
        <div className="detail-actions">
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

      {!bundleLoading && !ingestedTotal && !feed.total ? (
        <p className="user-empty">No post found for this user.</p>
      ) : null}

      {postsLoaded && feed.counts.all ? (
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

      {bundleLoading ? (
        <LoadingScreen label={`Loading posts for @${username}`} />
      ) : (
        <>
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

          {postsLoaded && !rows.length && feed.total ? (
            <p className="user-empty">No post in this tab.</p>
          ) : null}

          {feed.remaining ? (
            <div className="feed-more">
              <button
                type="button"
                className="feed-more-btn"
                disabled={loadingMore}
                onClick={() => void loadMore()}
              >
                {loadingMore ? "Loading…" : "Load more"}
              </button>
              <span className="feed-more-label">
                {rows.length} of {feed.total} posts in this feed
                {ingestedTotal > feed.total
                  ? ` · ${ingestedTotal} ingested in graph`
                  : ""}
              </span>
            </div>
          ) : rows.length > USER_FEED_BATCH ? (
            <p className="feed-end">All {feed.total} posts in this feed shown.</p>
          ) : null}
        </>
      )}
    </div>
  );
}
