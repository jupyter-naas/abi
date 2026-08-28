"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { hrefFor } from "@/lib/routes";
import {
  rankTweets,
  TWEET_RESULTS_PAGE_SIZE,
  type TweetHit,
} from "@/lib/tweetSearch";

type Props = {
  hits: TweetHit[];
  needle: string;
  onNeedleChange: (needle: string) => void;
  /** Result page, 0-based. */
  page: number;
  onPageChange: (page: number) => void;
  timezone: string;
};

function formatInstant(iso: string, timezone: string): string {
  if (!iso) return "";
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

/**
 * The Search Tweets page: the published posts as a list of results.
 *
 * Built like the Users search: the address, then the post's id and author as
 * the title that links to it, then its own text as the snippet - and under
 * that, when it was posted and the query, as written, that pulled it in. The
 * box is typed freely and submitted with Enter (Google style); typing does not
 * re-filter.
 *
 * A hit's title opens the post on its own page (`/posts/post/?post=…`) and its
 * author opens their feed. The way out to x.com is on the post's own page,
 * not on every row of a list.
 */
export function TweetResults({
  hits,
  needle,
  onNeedleChange,
  page,
  onPageChange,
  timezone,
}: Props) {
  const { data } = useAppState();
  const graph = data?.graph || null;
  // The *query as written* - what was actually sent to X - not its slug: the
  // meta line under a result is where you check why the post is here.
  const queryString = (slug: string) => {
    const entry = (data?.queries || []).find((q) => q.slug === slug);
    return entry?.query || entry?.label || slug;
  };
  // What is in the box, which only becomes the query on Enter / clear.
  const [draft, setDraft] = useState(needle);
  useEffect(() => {
    setDraft(needle);
  }, [needle]);

  const submitted = needle.trim();
  const matches = useMemo(() => rankTweets(hits, submitted), [hits, submitted]);
  const browsable = matches.length;
  const graphTotal = graph?.posts ?? null;
  const publishIsPartial =
    !submitted &&
    graphTotal != null &&
    graphTotal > browsable;

  const goToPage = (next: number) => {
    onPageChange(next);
    window.scrollTo({ top: 0 });
  };

  const pages = Math.max(1, Math.ceil(matches.length / TWEET_RESULTS_PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const start = current * TWEET_RESULTS_PAGE_SIZE;
  const listed = matches.slice(start, start + TWEET_RESULTS_PAGE_SIZE);

  return (
    <div className="results">
      <form
        className="results-search"
        onSubmit={(e) => {
          e.preventDefault();
          onNeedleChange(draft);
        }}
      >
        <svg className="results-search-ico" viewBox="0 0 24 24" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3.5-3.5" />
        </svg>
        <input
          className="results-input"
          type="search"
          placeholder="Search the posts, an author or a location…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoComplete="off"
          enterKeyHint="search"
          aria-label="Search tweets"
        />
        {draft ? (
          <button
            type="button"
            className="results-clear"
            title="Clear search"
            aria-label="Clear search"
            onClick={() => {
              setDraft("");
              onNeedleChange("");
            }}
          >
            ×
          </button>
        ) : null}
      </form>

      {/* Unsearched, quote the graph size when we have it - but paging always
          follows the rows this publish actually carries (newest 1 000 per query
          + window), so say both when they differ. */}
      <p className="results-count">
        {submitted
          ? `${browsable.toLocaleString()} result${
              browsable === 1 ? "" : "s"
            } for “${submitted}”`
          : publishIsPartial
            ? `${browsable.toLocaleString()} newest post${
                browsable === 1 ? "" : "s"
              } in this publish (${graphTotal.toLocaleString()} in the X graph)`
            : graphTotal != null
              ? `${graphTotal.toLocaleString()} post${
                  graphTotal === 1 ? "" : "s"
                } in the X graph`
              : `${browsable.toLocaleString()} published post${
                  browsable === 1 ? "" : "s"
                }`}
        {pages > 1 ? ` · page ${current + 1}/${pages.toLocaleString()}` : ""}
      </p>

      {!listed.length ? (
        <p className="user-empty">
          {hits.length
            ? "No post matches - try a shorter word, an author or a location."
            : "No post in this publish yet."}
        </p>
      ) : null}

      <ol className="result-list" start={start + 1}>
        {listed.map((hit, index) => {
          // The title identifies the post: which post, by whom. Everything
          // else about it goes under the text it is a title for.
          const title = [hit.id, hit.username ? `@${hit.username}` : ""]
            .filter(Boolean)
            .join(" - ");
          const facts = [
            formatInstant(hit.createdAt, timezone),
            hit.referenced ? "Referenced" : "",
            hit.location,
            hit.mediaCount ? `${hit.mediaCount} media` : "",
          ].filter(Boolean);
          return (
            <li className="result" key={hit.id || hit.url || start + index}>
              <div className="result-main">
                {/* The address, with the author as the way to their feed -
                    the same jump a Search Users result makes. */}
                <span className="result-url">
                  x.com ›{" "}
                  {hit.username ? (
                    <Link
                      className="result-author"
                      href={hrefFor("users", { user: hit.username })}
                    >
                      {hit.username}
                    </Link>
                  ) : (
                    "-"
                  )}
                  {hit.id ? ` › status/${hit.id}` : ""}
                </span>
                {/* A `<Link>`, not an `<a>`: this crosses to another page, so
                    the href needs Next's `basePath` in front of it. `from`
                    carries where the reader came from, so the post page's back
                    link returns to this search rather than to the author. */}
                {hit.id ? (
                  <Link
                    className="result-title"
                    href={hrefFor("post", {
                      post: hit.id,
                      user: hit.username,
                      from: "tweets",
                      q: submitted,
                    })}
                  >
                    {title || "-"}
                  </Link>
                ) : (
                  <span className="result-title as-text">{title || "-"}</span>
                )}
                <p className="result-snippet">{hit.text || "-"}</p>
                {facts.length ? (
                  <p className="result-facts">{facts.join(" · ")}</p>
                ) : null}
                {hit.queries.length ? (
                  <p className="result-meta">
                    <span className="result-meta-label">query:</span>{" "}
                    <span className="result-query">
                      {hit.queries.map(queryString).join("  ·  ")}
                    </span>
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>

      {matches.length > TWEET_RESULTS_PAGE_SIZE ? (
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
