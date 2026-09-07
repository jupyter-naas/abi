"use client";

import Link from "next/link";
import { useAppState } from "@/components/AppProvider";
import { MediaCarousel } from "@/components/MediaCarousel";
import { FEED } from "@/lib/appConfig";
import { hrefFor } from "@/lib/routes";
import { postAnchorId, tweetIdOf } from "@/lib/userSearch";
import type { TweetRow } from "@/lib/types";

type Props = {
  post: TweetRow;
  username: string;
  needle: string;
  timezone: string;
  /** True while this post is the one open on its own page. */
  selected: boolean;
  /**
   * Rendered expanded: the post alone on the page, so nothing is clipped and
   * nothing is a link to itself.
   */
  expanded?: boolean;
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

export function UserPostCard({
  post,
  username,
  needle,
  timezone,
  selected,
  expanded = false,
}: Props) {
  const { data } = useAppState();
  const tweetId = tweetIdOf(post);
  // The post's own page: the tweet id is the address, the author a shortcut.
  const postHref = tweetId
    ? hrefFor("post", {
        post: tweetId,
        user: post.username || username,
        from: "users",
      })
    : null;
  // The card wears the same word as the tab that holds it (`feed.tabs`).
  const label = (key: string) =>
    FEED.tabs.find((tab) => tab.key === key)?.label || key;
  const kind = post.referenced ? label("referenced") : label("matched");
  // Which followed queries pulled this post in, named as the filters name them.
  const queries = (post.queries || []).map((slug) => {
    const entry = (data?.queries || []).find((q) => q.slug === slug);
    return entry?.label || entry?.query || slug;
  });
  const media = (post.media_url || "").trim();

  return (
    <article
      // The scroll target: closing the expanded post comes back to this card,
      // so it needs an id the feed can find it by.
      id={tweetId ? postAnchorId(tweetId) : undefined}
      className={`user-post${selected ? " selected" : ""}${
        expanded ? " expanded" : ""
      }`}
    >
      {/* Date first, then the URL: the feed reads as a timeline, and the link
          is the detail under it. */}
      <p className="user-post-meta">
        <span>{formatInstant(post.created_at, timezone)}</span>
        <span className="user-post-sep">|</span>
        <span className={post.referenced ? "kind-context" : "kind-matched"}>
          {kind}
        </span>
        {queries.length ? (
          <>
            <span className="user-post-sep">·</span>
            <span className="user-post-queries">{queries.join(", ")}</span>
          </>
        ) : null}
        {/* A real link to a real page: ⌘-click opens the post in its own tab,
            and the address is shareable as it stands. */}
        {expanded || !postHref ? null : (
          <Link
            className="user-post-expand"
            href={postHref}
            title="Open this post on its own page"
            aria-label="Open this post on its own page"
          >
            ⤢
          </Link>
        )}
      </p>
      {post.url ? (
        // Expanded, the URL is the way out to x.com; in the feed it opens the
        // post's own page, like everything else on the card.
        expanded || !postHref ? (
          <a
            className="user-post-url"
            href={post.url}
            target="_blank"
            rel="noreferrer"
          >
            {post.url}
          </a>
        ) : (
          <Link className="user-post-url" href={postHref}>
            {post.url}
          </Link>
        )
      ) : (
        <span className="user-post-url muted">no url</span>
      )}
      {/* In the feed the body is a second way in: readers reach for the post,
          not for its URL. */}
      {expanded || !postHref ? (
        <p className="user-post-text">{post.text || "-"}</p>
      ) : (
        <Link className="user-post-text clickable" href={postHref}>
          {post.text || "-"}
        </Link>
      )}
      {media ? <MediaCarousel value={media} /> : null}
    </article>
  );
}
