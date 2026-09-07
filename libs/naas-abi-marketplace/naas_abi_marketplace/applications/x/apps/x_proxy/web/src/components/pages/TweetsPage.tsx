"use client";

import { useMemo, useState } from "react";
import { TweetResults } from "@/components/TweetResults";
import { tweetHits } from "@/lib/tweetSearch";
import type { Snapshots } from "@/lib/types";

type Props = {
  data: Snapshots["search"];
  timezone: string;
  /** What the search box is looking for, mirrored in `?q=`. */
  needle: string;
  onNeedleChange: (needle: string) => void;
};

/**
 * The Search Tweets page.
 *
 * Like Search Users, it is **not** scoped by the Scenario / Query filters: it
 * searches every post the publish carries, and each result names the query that
 * pulled it in and when it was posted. Nothing is fetched - the rows are the
 * ones `tables.json` already loaded.
 */
export function TweetsPage({ data, timezone, needle, onNeedleChange }: Props) {
  const [page, setPage] = useState(0);
  const hits = useMemo(() => tweetHits(data.tables), [data.tables]);

  // A new needle starts again at the first page of results.
  const handleNeedleChange = (value: string) => {
    onNeedleChange(value);
    setPage(0);
  };

  return (
    <TweetResults
      hits={hits}
      needle={needle}
      onNeedleChange={handleNeedleChange}
      page={page}
      onPageChange={setPage}
      timezone={timezone}
    />
  );
}
