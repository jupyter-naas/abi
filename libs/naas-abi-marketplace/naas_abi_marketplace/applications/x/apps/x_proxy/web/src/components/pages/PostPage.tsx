"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { UserPostCard } from "@/components/UserPostCard";
import { hrefFor } from "@/lib/routes";
import { postLink } from "@/lib/pins";
import { findHit, hitAsRow } from "@/lib/tweetSearch";
import { findPost, loadUserBundle } from "@/lib/userSearch";
import type { Snapshots, TweetRow, UserBundle } from "@/lib/types";

type Props = {
  data: Snapshots["search"];
  timezone: string;
  /** `?post=` - the page's subject. Without it there is nothing to show. */
  postId: string | null;
  /** `?user=` - optional: it names the shard to read instead of searching. */
  username: string | null;
  /** `?from=` - which page this was opened from: `tweets` or `users`. */
  from: string | null;
  /** `?q=` - the search the post was found in, so back restores it. */
  needle: string;
  /** `?expand=1` - the post alone, with none of the app's chrome around it. */
  expanded: boolean;
  /**
   * Enters or leaves the full view.
   *
   * Needed because the toggle only changes the query string of the page it is
   * on: Next keeps the same component mounted and fires no popstate, so the
   * view would never hear about it. Modified clicks are left to the browser,
   * which is what the link's `href` is for.
   */
  onExpandChange: (expanded: boolean) => void;
};

/**
 * One post, on its own page.
 *
 * The tweet id is the whole address: `/posts/post/?post=<id>`. The author is
 * optional and only ever a shortcut - given one, the post comes from that
 * author's shard (one file); without one, it is found among the published rows,
 * which also names the author. Only a post outside every published window needs
 * `?user=` to be found at all.
 *
 * `?from=` says which page opened it, so back returns there - the search that
 * found the post, or the author's feed it was expanded in. Whichever back does
 * not lead to is still reachable: the author's feed keeps a link of its own.
 */
export function PostPage({
  data,
  timezone,
  postId,
  username,
  from,
  needle,
  expanded,
  onExpandChange,
}: Props) {
  const { pinnedIds, togglePinned } = useAppState();
  // The published rows are already in memory, so this costs nothing.
  const hit = useMemo(() => findHit(data.tables, postId), [data.tables, postId]);
  const author = username || hit?.username || null;

  const [bundle, setBundle] = useState<UserBundle | null>(null);
  const [loading, setLoading] = useState(Boolean(author));

  // The shard carries the whole post - full text, every media - where a table
  // row carries what the table needed. Given an author, prefer it.
  useEffect(() => {
    if (!author) {
      setLoading(false);
      return;
    }
    let live = true;
    setLoading(true);
    loadUserBundle(author)
      .then((res) => {
        if (live) setBundle(res);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [author]);

  // Opened from the Search Tweets results: back belongs to that search.
  const toSearch = from === "tweets";
  // The same post, with and without the app around it.
  const selfHref = (expand: boolean) =>
    hrefFor("post", {
      post: postId,
      user: username,
      from,
      q: needle,
      expand,
    });

  const post: TweetRow | null =
    findPost(bundle, postId) || (hit ? hitAsRow(hit) : null);
  const pinned = Boolean(postId) && pinnedIds.posts.includes(`p:${postId}`);

  if (!postId) {
    return (
      <div className="detail">
        <p className="user-empty">
          No post named - this page opens one post, as{" "}
          <code>?post=&lt;tweet id&gt;</code>.
        </p>
      </div>
    );
  }

  return (
    <div className={`detail${expanded ? " post-full" : ""}`}>
      <div className="detail-head">
        {/* Back goes where the reader came from: the search that found the
            post, or the author whose feed it was expanded in. The other one is
            still on the page, as a link of its own. */}
        {toSearch ? (
          <Link
            className="detail-back"
            href={hrefFor("tweets", { q: needle })}
          >
            ◂ Back to Search Tweets
          </Link>
        ) : author ? (
          <Link className="detail-back" href={hrefFor("users", { user: author })}>
            ◂ Back to @{author}
          </Link>
        ) : (
          <Link className="detail-back" href={hrefFor("tweets", {})}>
            ◂ Back to Search Tweets
          </Link>
        )}
        <div className="detail-actions">
          {/* Top right: the post with nothing around it, and the way back from
              it. It is a URL, so a full view can be linked to directly. */}
          <Link
            className="post-expand"
            href={selfHref(!expanded)}
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
          {/* Pins the *post*, to the posts bar this page carries - never to
              the authors pinned on Users. The two bars are separate. */}
          {postId ? (
            <button
              type="button"
              className={`pin-toggle${pinned ? " pinned" : ""}`}
              onClick={() =>
                togglePinned(
                  "posts",
                  postLink(postId, author || "", post?.text || "", from, needle),
                )
              }
              title={pinned ? "Unpin this post" : "Pin this post"}
              aria-pressed={pinned}
            >
              {pinned ? "★ Pinned" : "☆ Pin"}
            </button>
          ) : null}
          {toSearch && author ? (
            <Link className="result-open" href={hrefFor("users", { user: author })}>
              @{author}&apos;s feed
            </Link>
          ) : null}
          {post?.url ? (
            <a
              className="result-open"
              href={post.url}
              target="_blank"
              rel="noreferrer"
            >
              ↗ On X
            </a>
          ) : null}
        </div>
      </div>

      {loading && !post ? <p className="user-empty">Loading the post…</p> : null}

      {post ? (
        <UserPostCard
          post={post}
          username={author || post.username || ""}
          needle=""
          timezone={timezone}
          selected
          expanded
        />
      ) : loading ? null : (
        <p className="user-empty">
          Post {postId} is not in the published dataset. It may be outside every
          published window - add <code>&amp;user=&lt;handle&gt;</code> to open it
          from that author&apos;s posts.
        </p>
      )}
    </div>
  );
}
