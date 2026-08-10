"use client";

import { useEffect, useMemo, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { KpiGrid } from "@/components/KpiGrid";
import { UserProfileCard } from "@/components/UserProfileCard";
import {
  loadUserBundle,
  loadUserIndex,
  pageOf,
  USER_POSTS_PAGE_SIZE,
} from "@/lib/userSearch";
import { searchFor } from "@/lib/routes";
import type {
  KpiItem,
  TableEntry,
  UserBundle,
  UserRow,
} from "@/lib/types";

type Props = {
  timezone: string;
  /** Author deep-linked by `?user=` in the URL; `null` shows the picker only. */
  selected: string | null;
  onSelectUser: (username: string | null) => void;
};

/** Users listed at once; the search box narrows below this. */
const MAX_LISTED_USERS = 200;

const POSTS_COLUMNS = [
  { key: "created_at", label: "Date" },
  { key: "text", label: "Text" },
  { key: "url", label: "URL" },
  { key: "media_url", label: "Media" },
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

export function UsersPage({ timezone, selected, onSelectUser }: Props) {
  const [needle, setNeedle] = useState("");
  const [users, setUsers] = useState<UserRow[]>([]);
  const [indexLoading, setIndexLoading] = useState(true);
  const [bundle, setBundle] = useState<UserBundle | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  // The picker index is every author in the tweet graph — a few MB, fetched
  // once when the page first opens and memoised for the rest of the session.
  useEffect(() => {
    let live = true;
    loadUserIndex()
      .then((index) => {
        if (live) setUsers(index.users);
      })
      .finally(() => {
        if (live) setIndexLoading(false);
      });
    return () => {
      live = false;
    };
  }, []);

  const matches = useMemo(() => {
    const q = needle.trim().toLowerCase();
    if (!q) return users;
    return users.filter(
      (u) =>
        u.username.toLowerCase().includes(q) ||
        (u.location || "").toLowerCase().includes(q),
    );
  }, [users, needle]);
  const listed = matches.slice(0, MAX_LISTED_USERS);

  // Selecting a user fetches the one shard holding their posts; paging then
  // slices that already-loaded list, so it costs nothing.
  useEffect(() => {
    setOffset(0);
    if (!selected) {
      setBundle(null);
      return;
    }
    let live = true;
    setLoading(true);
    loadUserBundle(selected)
      .then((res) => {
        if (live) setBundle(res);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [selected]);

  const page = useMemo(() => pageOf(bundle, offset), [bundle, offset]);
  const known = users.find((u) => u.username === selected) || null;
  const profile = page.profile || known;
  const total = page.total || known?.posts || 0;
  const rows = page.rows;
  const lastPostAt = profile?.last_post_at || rows[0]?.created_at || "";
  const firstPostAt = page.profile?.first_post_at || "";

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

  /** Clicking the active author clears the selection, and the URL with it. */
  const select = (username: string) => {
    onSelectUser(selected === username ? null : username);
  };

  // The picker rows are real links, so ctrl / cmd / middle click must keep the
  // browser's own "open in a new tab" behaviour instead of selecting in place.
  const handleItemClick = (
    event: React.MouseEvent<HTMLAnchorElement>,
    username: string,
  ) => {
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
    select(username);
  };

  // A handle typed into the URL may simply not be in the published dataset.
  const unknownUser =
    !!selected && !indexLoading && !loading && !profile && !rows.length;

  return (
    <div>
      <div className="section">
        <div className="section-head">
          <h2>Find a user</h2>
          <p className="sub">
            {indexLoading
              ? "Loading the author index…"
              : `${matches.length.toLocaleString()} user(s) in the X graph · select one to see all their posts`}
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
              <p className="user-empty">
                {indexLoading ? "Loading…" : "No user matches."}
              </p>
            ) : (
              listed.map((u) => (
                <a
                  key={u.username}
                  // Relative to /users/search/ — the row never leaves the page.
                  href={searchFor("users", { user: u.username })}
                  className={`user-item${u.username === selected ? " active" : ""}`}
                  onClick={(e) => handleItemClick(e, u.username)}
                >
                  <span className="user-name">@{u.username}</span>
                  <span className="user-meta">
                    {u.posts.toLocaleString()} post(s)
                    {u.location ? ` · ${u.location}` : ""}
                    {u.verified_type ? ` · ${u.verified_type}` : ""}
                  </span>
                </a>
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
          <UserProfileCard
            profile={profile}
            username={selected}
            timezone={timezone}
          />
          <div className="section">
            <div className="section-head">
              <h2>Posts published by @{selected}</h2>
              <p className="sub">
                {loading
                  ? "Loading posts…"
                  : total
                    ? `${pageStart.toLocaleString()}–${pageEnd.toLocaleString()} of ${total.toLocaleString()} post(s), newest first`
                    : unknownUser
                      ? `@${selected} is not in the published X graph — check the handle in the URL.`
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
