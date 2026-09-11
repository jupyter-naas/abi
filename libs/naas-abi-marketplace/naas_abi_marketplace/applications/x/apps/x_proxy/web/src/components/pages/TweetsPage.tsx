"use client";

import { useEffect, useState } from "react";
import { TweetResults } from "@/components/TweetResults";
import {
  loadTweetPreview,
  loadTweetSearchPage,
  type TweetHit,
  type TweetSearchPage,
} from "@/lib/tweetSearch";

type Props = {
  timezone: string;
  /** What the search box is looking for, mirrored in `?q=`. */
  needle: string;
  onNeedleChange: (needle: string) => void;
};

/**
 * The Search Tweets page.
 *
 * Like Search Users, it is **not** scoped by the Scenario / Query filters: it
 * searches every post in the tweet graph. The preview (newest 1 000 posts)
 * loads on mount for a fast first paint; the full whole-graph index is
 * fetched once a needle is submitted, so browsing the unsearched list never
 * pays for it.
 */
export function TweetsPage({ timezone, needle, onNeedleChange }: Props) {
  const [page, setPage] = useState(0);
  const [preview, setPreview] = useState<TweetHit[]>([]);
  const [remote, setRemote] = useState<TweetSearchPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    loadTweetPreview().then((hits) => {
      if (live) setPreview(hits);
    });
    return () => {
      live = false;
    };
  }, []);

  const submitted = needle.trim();
  useEffect(() => {
    if (!submitted && page === 0) {
      setRemote(null);
      setError("");
      return;
    }
    let live = true;
    setLoading(true);
    setError("");
    loadTweetSearchPage(submitted, page)
      .then((result) => {
        if (live) setRemote(result);
      })
      .catch((reason: unknown) => {
        if (live) {
          setRemote(null);
          setError(reason instanceof Error ? reason.message : "Search failed");
        }
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [submitted, page]);

  const serverPaged = Boolean(submitted || page > 0);
  const hits = serverPaged ? remote?.hits || [] : preview;

  // A new needle starts again at the first page of results.
  const handleNeedleChange = (value: string) => {
    onNeedleChange(value);
    setRemote(null);
    setPage(0);
  };

  const handlePageChange = (value: number) => {
    setRemote(null);
    setPage(value);
  };

  return (
    <TweetResults
      hits={hits}
      loading={loading}
      error={error}
      total={remote?.count}
      serverPaged={serverPaged}
      needle={needle}
      onNeedleChange={handleNeedleChange}
      page={page}
      onPageChange={handlePageChange}
      timezone={timezone}
    />
  );
}
