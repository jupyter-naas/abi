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
  selected: boolean;
  onSelect: (tweetId: string) => void;
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
    if (!isPlainClick(e) || !tweetId) return;
    e.preventDefault();
    onSelect(tweetId);
  };

  return (
    <article
      // The scroll target: selecting a post aligns this element to the top of
      // the page, so it needs an id the page can find it by.
      id={tweetId ? postAnchorId(tweetId) : undefined}
      className={`user-post${selected ? " selected" : ""}`}
    >
      {post.url ? (
        <a className="user-post-url" href={href} onClick={select}>
          {post.url}
        </a>
      ) : (
        <span className="user-post-url muted">no url</span>
      )}
      <p className="user-post-meta">
        <span>{formatInstant(post.created_at, timezone)}</span>
        <span className="user-post-sep">|</span>
        <span>{kind}</span>
      </p>
      {/* The body is a second click target for the same thing: readers reach
          for the post, not for its URL. */}
      <p
        className={`user-post-text${tweetId ? " clickable" : ""}`}
        onClick={select}
      >
        {post.text || "—"}
      </p>
      {media ? <MediaCarousel value={media} /> : null}
    </article>
  );
}
