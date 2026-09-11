"use client";

import { useEffect, useState } from "react";
import { TweetResults } from "@/components/TweetResults";
import { loadTweetIndex, loadTweetPreview, type TweetHit } from "@/lib/tweetSearch";

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
  const [full, setFull] = useState<TweetHit[] | null>(null);
  const [loadingFull, setLoadingFull] = useState(false);

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
    if (!submitted || full) return;
    let live = true;
    setLoadingFull(true);
    loadTweetIndex()
      .then((hits) => {
        if (live) setFull(hits);
      })
      .finally(() => {
        if (live) setLoadingFull(false);
      });
    return () => {
      live = false;
    };
  }, [submitted, full]);

  const hits = full || preview;

  // A new needle starts again at the first page of results.
  const handleNeedleChange = (value: string) => {
    onNeedleChange(value);
    setPage(0);
  };

  return (
    <TweetResults
      hits={hits}
      loading={loadingFull && !full}
      needle={needle}
      onNeedleChange={handleNeedleChange}
      page={page}
      onPageChange={setPage}
      timezone={timezone}
    />
  );
}
