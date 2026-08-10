"use client";

import { useEffect, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { DataTable } from "@/components/DataTable";
import { KpiGrid } from "@/components/KpiGrid";
import { UserProfileCard } from "@/components/UserProfileCard";
import {
  loadUserBundle,
  pageOf,
  USER_POSTS_PAGE_SIZE,
} from "@/lib/userSearch";
import type {
  KpiItem,
  TableEntry,
  UserBundle,
  UserRow,
} from "@/lib/types";

type Props = {
  username: string;
  /** The index row for this author, when the search index knows them. */
  known: UserRow | null;
  indexLoading: boolean;
  timezone: string;
  /** Closes the page and returns to the search results it was opened from. */
  onClose: () => void;
};

const POSTS_COLUMNS = [
  { key: "created_at", label: "Date" },
  { key: "text", label: "Post" },
  { key: "url", label: "URL" },
];

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
 * memory rather than another fetch.
 */
export function UserDetail({
  username,
  known,
  indexLoading,
  timezone,
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

  const page = pageOf(bundle, offset);
  const profile = page.profile || known;
  const total = page.total || known?.posts || 0;
  const rows = page.rows;
  const lastPostAt = profile?.last_post_at || rows[0]?.created_at || "";
  const firstPostAt = page.profile?.first_post_at || "";
  const pinned = pinnedUsers.includes(username);
  // A handle typed into the URL may simply not be in the published dataset.
  const unknown = !indexLoading && !loading && !profile && !rows.length;

  const kpis: KpiItem[] = [
    {
      id: "posts_retrieved",
      label: "Posts retrieved",
      value: total,
      hint: "all posts in the X graph",
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

  const postsTable: TableEntry = {
    id: "user_posts",
    query_slug: username,
    scenario_id: String(offset),
    columns: POSTS_COLUMNS,
    rows: rows as unknown as Record<string, unknown>[],
  };

  const pageStart = rows.length ? offset + 1 : 0;
  const pageEnd = offset + rows.length;

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

      <div className="section">
        <div className="section-head">
          <h2>Posts ingested</h2>
          <p className="sub">Counted over the whole X graph, not this page.</p>
        </div>
        <KpiGrid items={kpis} columns={3} accentFirst />
      </div>

      <div className="section">
        <div className="section-head">
          <h2>Posts published by @{username}</h2>
          <p className="sub">
            {loading
              ? "Loading posts…"
              : total
                ? `${pageStart.toLocaleString()}–${pageEnd.toLocaleString()} of ${total.toLocaleString()} post(s), newest first`
                : "No post found for this user."}
          </p>
        </div>
        <div className="card">
          <DataTable table={postsTable} timezone={timezone} nestUrlUnderText />
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
        </div>
      </div>
    </div>
  );
}
