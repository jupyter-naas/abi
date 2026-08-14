"use client";

import { MediaBelowPost } from "@/components/DataTable";
import { searchFor } from "@/lib/routes";
import { tweetIdOf } from "@/lib/userSearch";
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

  return (
    <article className={`user-post${selected ? " selected" : ""}`}>
      {post.url ? (
        <a
          className="user-post-url"
          href={href}
          onClick={(e) => {
            if (
              !tweetId ||
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
            onSelect(tweetId);
          }}
        >
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
      <p className="user-post-text">{post.text || "—"}</p>
      {media ? <MediaBelowPost value={media} /> : null}
    </article>
  );
}
