"use client";

import { MediaCarousel } from "@/components/MediaCarousel";
import { searchFor } from "@/lib/routes";
import { postAnchorId, tweetIdOf } from "@/lib/userSearch";
import type { TweetRow } from "@/lib/types";

type Props = {
  post: TweetRow;
  username: string;
  needle: string;
  timezone: string;
  /** True while this post is the one open on its own page. */
  selected: boolean;
  /** Opens the post on its own page. */
  onSelect: (tweetId: string) => void;
  /**
   * Rendered expanded: the post alone on the page, so nothing is clipped and
   * nothing is a link to itself.
   */
  expanded?: boolean;
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

export function UserPostCard({
  post,
  username,
  needle,
  timezone,
  selected,
  onSelect,
  expanded = false,
}: Props) {
  const tweetId = tweetIdOf(post);
  const kind = post.referenced ? "Context" : "Matched";
  const href = tweetId
    ? searchFor("users", { q: needle, user: username, post: tweetId })
    : post.url;
  const media = (post.media_url || "").trim();

  /**
   * True for the plain left-click that means "bring this post to the top".
   *
   * Modified clicks are the browser's — they open the deep link in a tab of
   * its own, which is what the `href` is there for.
   */
  const isPlainClick = (e: React.MouseEvent) =>
    Boolean(tweetId) &&
    !e.defaultPrevented &&
    e.button === 0 &&
    !e.metaKey &&
    !e.ctrlKey &&
    !e.shiftKey &&
    !e.altKey;

  const select = (e: React.MouseEvent) => {
    if (expanded || !isPlainClick(e) || !tweetId) return;
    e.preventDefault();
    onSelect(tweetId);
  };

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
        {expanded ? null : (
          <button
            type="button"
            className="user-post-expand"
            onClick={(e) => select(e)}
            disabled={!tweetId}
            title="Open this post on its own page"
          >
            ⤢ Expand
          </button>
        )}
      </p>
      {post.url ? (
        // Expanded, the URL is the way out to x.com; in the feed a plain click
        // opens the post here instead, and a modified one follows the deep link.
        <a
          className="user-post-url"
          href={expanded ? post.url : href}
          target={expanded ? "_blank" : undefined}
          rel={expanded ? "noreferrer" : undefined}
          onClick={select}
        >
          {post.url}
        </a>
      ) : (
        <span className="user-post-url muted">no url</span>
      )}
      {/* In the feed the body is a second click target for the same thing:
          readers reach for the post, not for its URL. */}
      <p
        className={`user-post-text${tweetId && !expanded ? " clickable" : ""}`}
        onClick={select}
      >
        {post.text || "—"}
      </p>
      {media ? <MediaCarousel value={media} /> : null}
    </article>
  );
}
