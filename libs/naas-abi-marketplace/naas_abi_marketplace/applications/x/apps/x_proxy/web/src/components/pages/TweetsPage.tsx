"use client";

import { useEffect, useState } from "react";
import { TweetResults } from "@/components/TweetResults";
import { loadTweetSearchPage, type TweetSearchPage } from "@/lib/tweetSearch";

type Props = {
  timezone: string;
  needle: string;
  onNeedleChange: (needle: string) => void;
};

/** Search Tweets — whole graph via dataset `search_tweets/query.json`. */
export function TweetsPage({ timezone, needle, onNeedleChange }: Props) {
  const [page, setPage] = useState(0);
  const [remote, setRemote] = useState<TweetSearchPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    loadTweetSearchPage(needle, page)
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
  }, [needle, page]);

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
      hits={remote?.hits || []}
      loading={loading}
      error={error}
      total={remote?.count}
      serverPaged
      needle={needle}
      onNeedleChange={handleNeedleChange}
      page={page}
      onPageChange={handlePageChange}
      timezone={timezone}
    />
  );
}
