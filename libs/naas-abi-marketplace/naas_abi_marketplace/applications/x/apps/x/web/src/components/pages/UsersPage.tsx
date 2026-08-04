"use client";

import { useEffect, useMemo, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { KpiGrid } from "@/components/KpiGrid";
import {
  fetchUserPosts,
  searchUsers,
  USER_POSTS_PAGE_SIZE,
  type UserPostsPage,
} from "@/lib/userSearch";
import type { KpiItem, Snapshots, TableEntry, UserRow } from "@/lib/types";

type Props = {
  users: Snapshots["users"];
  timezone: string;
};

/** Users listed at once; the search box narrows below this. */
const MAX_LISTED_USERS = 200;

const POSTS_COLUMNS = [
  { key: "created_at", label: "Date" },
  { key: "text", label: "Text" },
  { key: "url", label: "URL" },
  { key: "location", label: "Location" },
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

export function UsersPage({ users, timezone }: Props) {
  const [needle, setNeedle] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [liveMatches, setLiveMatches] = useState<UserRow[] | null>(null);
  const [page, setPage] = useState<UserPostsPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(false);

  // Published list — the picker's offline fallback, and what shows before the
  // first keystroke reaches the graph.
  const localMatches = useMemo(() => {
    const q = needle.trim().toLowerCase();
    if (!q) return users;
    return users.filter(
      (u) =>
        u.username.toLowerCase().includes(q) ||
        (u.location || "").toLowerCase().includes(q),
    );
  }, [users, needle]);

  // Every keystroke searches the whole tweet graph, so an author outside the
  // published top-N is still reachable.
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      searchUsers(needle, controller.signal)
        .then((res) => {
          setLiveMatches(res);
          setOffline(res === null);
        })
        .catch(() => {
          /* superseded by a newer keystroke */
        });
    }, 250);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [needle]);

  const matches = liveMatches ?? localMatches;
  const listed = matches.slice(0, MAX_LISTED_USERS);

  // Selecting a user, or paging, is one graph query: totals for the KPIs plus
  // that page of posts (newest first).
  useEffect(() => {
    if (!selected) {
      setPage(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    fetchUserPosts(selected, offset, controller.signal)
      .then((res) => {
        setPage(res);
        setOffline(res === null);
      })
      .catch(() => {
        /* superseded by a newer selection */
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [selected, offset]);

  const known = users.find((u) => u.username === selected) || null;
  const profile = page?.profile || known;
  const total = page?.total ?? known?.posts ?? 0;
  const rows = page?.rows || [];
  const lastPostAt = profile?.last_post_at || rows[0]?.created_at || "";
  const firstPostAt = page?.profile?.first_post_at || "";

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

  const postsTable: TableEntry | null = selected
    ? {
        id: "user_posts",
        query_slug: selected,
        scenario_id: String(offset),
        columns: POSTS_COLUMNS,
        rows: rows as unknown as Record<string, unknown>[],
      }
    : null;

  const pageStart = rows.length ? offset + 1 : 0;
  const pageEnd = offset + rows.length;
  const hasPrev = offset > 0;
  const hasNext = pageEnd < total;

  const select = (username: string) => {
    setSelected((prev) => (prev === username ? null : username));
    setOffset(0);
  };

  return (
    <div>
      <div className="section">
        <div className="section-head">
          <h2>Find a user</h2>
          <p className="sub">
            {matches.length.toLocaleString()} user(s)
            {offline ? " in the published list" : " in the X graph"} · select one
            to see all their posts
          </p>
        </div>
        <div className="card">
          <input
            className="dt-search user-search"
            type="search"
            placeholder="Search a username…"
            value={needle}
            onChange={(e) => setNeedle(e.target.value)}
          />
          <div className="user-list">
            {!listed.length ? (
              <p className="user-empty">No user matches.</p>
            ) : (
              listed.map((u) => (
                <button
                  key={u.username}
                  type="button"
                  className={`user-item${u.username === selected ? " active" : ""}`}
                  onClick={() => select(u.username)}
                >
                  <span className="user-name">@{u.username}</span>
                  <span className="user-meta">
                    {u.posts.toLocaleString()} post(s)
                    {u.location ? ` · ${u.location}` : ""}
                    {u.verified_type ? ` · ${u.verified_type}` : ""}
                  </span>
                </button>
              ))
            )}
          </div>
          {matches.length > MAX_LISTED_USERS ? (
            <p className="dt-note">
              Showing the first {MAX_LISTED_USERS} of{" "}
              {matches.length.toLocaleString()} matching users — refine the
              search.
            </p>
          ) : null}
        </div>
      </div>

      {!selected ? (
        <p className="user-empty">Select a user to see their KPIs and posts.</p>
      ) : (
        <>
          <KpiGrid items={kpis} columns={3} accentFirst />
          <div className="section">
            <div className="section-head">
              <h2>Posts published by @{selected}</h2>
              <p className="sub">
                {loading
                  ? "Loading posts…"
                  : total
                    ? `${pageStart.toLocaleString()}–${pageEnd.toLocaleString()} of ${total.toLocaleString()} post(s), newest first`
                    : "No post found for this user."}
              </p>
            </div>
            <div className="card">
              <DataTable
                table={postsTable}
                timezone={timezone}
                nestUrlUnderText
              />
              <div className="pager">
                <button
                  type="button"
                  className="pager-btn"
                  disabled={!hasPrev || loading}
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
                  disabled={!hasNext || loading}
                  onClick={() => setOffset((o) => o + USER_POSTS_PAGE_SIZE)}
                >
                  Next ▸
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
