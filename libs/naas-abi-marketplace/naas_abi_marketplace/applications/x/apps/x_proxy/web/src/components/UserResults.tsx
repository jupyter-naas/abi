"use client";

import { useEffect, useState, type ReactNode } from "react";
import { highlightSearchNeedle } from "@/lib/highlightSearchNeedle";
import { searchFor } from "@/lib/routes";
import { USER_RESULTS_PAGE_SIZE } from "@/lib/userSearch";
import type { UserRow } from "@/lib/types";

type Props = {
  users: UserRow[];
  totalCount: number;
  needle: string;
  onNeedleChange: (needle: string) => void;
  /** Result page, 0-based. */
  page: number;
  onPageChange: (page: number) => void;
  onOpenUser: (username: string) => void;
  loading: boolean;
  error?: string;
  timezone: string;
};

function formatDate(iso: string, timezone: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      timeZone: timezone,
      year: "numeric",
      month: "short",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

/**
 * The Users search page: a list of results, not a grid of tiles.
 *
 * Each result reads like a search hit - the account's address, its display
 * name as the link with the handle under it, then a line of what the graph
 * knows about it. Pinning is on the author's own page, not on every row. The box is typed freely and submitted with Enter (Google
 * style); an empty submitted query lists the busiest authors, 100 per page.
 */
export function UserResults({
  users,
  totalCount,
  needle,
  onNeedleChange,
  page,
  onPageChange,
  onOpenUser,
  loading,
  error = "",
  timezone,
}: Props) {
  // What is in the box, which only becomes the query on Enter / clear.
  const [draft, setDraft] = useState(needle);
  useEffect(() => {
    setDraft(needle);
  }, [needle]);

  const submitted = needle.trim();
  const listed = users;

  const goToPage = (next: number) => {
    onPageChange(next);
    window.scrollTo({ top: 0 });
  };

  const pages = Math.max(1, Math.ceil(totalCount / USER_RESULTS_PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const start = current * USER_RESULTS_PAGE_SIZE;

  const submit = (value: string) => {
    onNeedleChange(value);
  };

  return (
    <div className="results">
      <form
        className="results-search"
        onSubmit={(e) => {
          e.preventDefault();
          submit(draft);
        }}
      >
        <svg className="results-search-ico" viewBox="0 0 24 24" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3.5-3.5" />
        </svg>
        <input
          className="results-input"
          type="search"
          placeholder="Search a username or a location…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoComplete="off"
          enterKeyHint="search"
          aria-label="Search users"
        />
        {draft ? (
          <button
            type="button"
            className="results-clear"
            title="Clear search"
            aria-label="Clear search"
            onClick={() => {
              setDraft("");
              submit("");
            }}
          >
            ×
          </button>
        ) : null}
      </form>

      <p className="results-count">
        {loading
          ? "Loading authors…"
          : `${totalCount.toLocaleString()} author${
              totalCount === 1 ? "" : "s"
            }${submitted ? ` for “${submitted}”` : " in the X graph"}`}
        {!loading && pages > 1
          ? ` · page ${current + 1}/${pages.toLocaleString()}`
          : ""}
      </p>

      {!loading && error ? (
        <p className="user-empty">Search unavailable: {error}</p>
      ) : null}

      {!loading && !error && !listed.length ? (
        <p className="user-empty">
          No author matches - try a shorter handle, or a location.
        </p>
      ) : null}

      <ol className="result-list" start={start + 1}>
        {listed.map((user) => {
          const factNodes: ReactNode[] = [
            `${user.posts.toLocaleString()} post${user.posts === 1 ? "" : "s"} ingested`,
            user.location
              ? highlightSearchNeedle(user.location, submitted)
              : "",
            user.verified_type && user.verified_type !== "none"
              ? user.verified_type
              : "",
            user.last_post_at
              ? `last post ${formatDate(user.last_post_at, timezone)}`
              : "",
          ].filter((part) => part !== "" && part != null);
          return (
            <li className="result" key={user.username}>
              <div className="result-main">
                <span className="result-url">
                  x.com ›{" "}
                  {highlightSearchNeedle(user.username, submitted)}
                </span>
                <a
                  className="result-title"
                  // Query-only, so it resolves against /users/search as it
                  // stands - no basePath to prepend, nothing to keep in sync.
                  href={searchFor("users", {
                    q: submitted,
                    user: user.username,
                  })}
                  onClick={(e) => {
                    if (
                      e.defaultPrevented ||
                      e.button !== 0 ||
                      e.metaKey ||
                      e.ctrlKey ||
                      e.shiftKey ||
                      e.altKey
                    ) {
                      return;
                    }
                    e.preventDefault();
                    onOpenUser(user.username);
                  }}
                >
                  {highlightSearchNeedle(
                    user.display_name || user.username,
                    submitted,
                  )}
                </a>
                <span className="result-handle">
                  @
                  {highlightSearchNeedle(user.username, submitted)}
                </span>
                {/* The bio is the snippet when the account has one; the facts
                    drop to their own line under it. Most authors are ingested
                    as tweet-author stubs and carry no bio at all. */}
                {user.description ? (
                  <p className="result-snippet">
                    {highlightSearchNeedle(user.description, submitted)}
                  </p>
                ) : null}
                <p className="result-facts">
                  {factNodes.map((part, i) => (
                    <span key={i}>
                      {i > 0 ? " · " : null}
                      {part}
                    </span>
                  ))}
                </p>
              </div>
            </li>
          );
        })}
      </ol>

      {totalCount > USER_RESULTS_PAGE_SIZE ? (
        <div className="pager">
          <button
            type="button"
            className="pager-btn"
            disabled={current === 0}
            onClick={() => goToPage(current - 1)}
          >
            ◂ Previous
          </button>
          <span className="pager-label">
            Page {current + 1} of {pages.toLocaleString()}
          </span>
          <button
            type="button"
            className="pager-btn"
            disabled={current >= pages - 1}
            onClick={() => goToPage(current + 1)}
          >
            Next ▸
          </button>
        </div>
      ) : null}
    </div>
  );
}
