"use client";

import { useEffect, useState } from "react";
import { UserDetail } from "@/components/UserDetail";
import { UserResults } from "@/components/UserResults";
import { loadUserIndex } from "@/lib/userSearch";
import type { UserRow } from "@/lib/types";

type Props = {
  timezone: string;
  /** Author deep-linked by `?user=`; `null` shows the search results. */
  selected: string | null;
  onSelectUser: (username: string | null) => void;
  /** Tweet id pinned on the author page, from `?post=`. */
  selectedPost: string | null;
  onSelectPost: (tweetId: string | null) => void;
  /** What the search box is looking for, mirrored in `?q=`. */
  needle: string;
  onNeedleChange: (needle: string) => void;
};

/**
 * The Users section: search results, or one author's page.
 *
 * The two are exclusive — opening an author replaces the results, closing it
 * brings them back with the needle intact, because both live in the URL.
 */
export function UsersPage({
  timezone,
  selected,
  onSelectUser,
  selectedPost,
  onSelectPost,
  needle,
  onNeedleChange,
}: Props) {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [indexLoading, setIndexLoading] = useState(true);
  const [resultsPage, setResultsPage] = useState(0);

  // The index is every author in the tweet graph — a few MB, fetched once when
  // the page first opens and memoised for the rest of the session.
  useEffect(() => {
    let live = true;
    loadUserIndex()
      .then((index) => {
        if (live) setUsers(index.users);
      })
      .finally(() => {
        if (live) setIndexLoading(false);
      });
    return () => {
      live = false;
    };
  }, []);

  // A new needle starts again at the first page of results.
  const handleNeedleChange = (value: string) => {
    onNeedleChange(value);
    setResultsPage(0);
  };

  if (selected) {
    return (
      <UserDetail
        username={selected}
        known={users.find((u) => u.username === selected) || null}
        indexLoading={indexLoading}
        timezone={timezone}
        needle={needle}
        selectedPost={selectedPost}
        onSelectPost={onSelectPost}
        onClose={() => onSelectUser(null)}
      />
    );
  }

  return (
    <UserResults
      users={users}
      needle={needle}
      onNeedleChange={handleNeedleChange}
      page={resultsPage}
      onPageChange={setResultsPage}
      onOpenUser={onSelectUser}
      loading={indexLoading}
      timezone={timezone}
    />
  );
}
