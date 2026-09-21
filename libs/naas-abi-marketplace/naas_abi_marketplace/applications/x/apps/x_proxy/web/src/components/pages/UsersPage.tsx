"use client";

import { useEffect, useState } from "react";
import { UserDetail } from "@/components/UserDetail";
import { UserResults } from "@/components/UserResults";
import { loadUserSearchPage } from "@/lib/userSearch";
import type { UserRow } from "@/lib/types";

type Props = {
  timezone: string;
  selected: string | null;
  onSelectUser: (username: string | null) => void;
  selectedPost: string | null;
  needle: string;
  onNeedleChange: (needle: string) => void;
  expanded: boolean;
  onExpandChange: (expanded: boolean) => void;
};

export function UsersPage({
  timezone,
  selected,
  onSelectUser,
  selectedPost,
  needle,
  onNeedleChange,
  expanded,
  onExpandChange,
}: Props) {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [resultsPage, setResultsPage] = useState(0);
  /** Row from the results list when opening a profile (avoids a second search.json). */
  const [knownFromList, setKnownFromList] = useState<UserRow | null>(null);

  useEffect(() => {
    if (selected) return;
    let live = true;
    setLoading(true);
    setError("");
    loadUserSearchPage(needle, resultsPage)
      .then((page) => {
        if (!live) return;
        setUsers(page.users);
        setTotalCount(page.count);
      })
      .catch((reason: unknown) => {
        if (!live) return;
        setUsers([]);
        setTotalCount(0);
        setError(reason instanceof Error ? reason.message : "Search failed");
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [needle, resultsPage, selected]);

  useEffect(() => {
    if (!selected) {
      setKnownFromList(null);
    }
  }, [selected]);

  const handleNeedleChange = (value: string) => {
    onNeedleChange(value);
    setResultsPage(0);
  };

  const handleOpenUser = (username: string) => {
    const row =
      users.find(
        (user) => user.username.toLowerCase() === username.toLowerCase(),
      ) ?? null;
    setKnownFromList(row);
    onSelectUser(username);
  };

  if (selected) {
    return (
      <UserDetail
        username={selected}
        known={knownFromList}
        timezone={timezone}
        needle={needle}
        selectedPost={selectedPost}
        expanded={expanded}
        onExpandChange={onExpandChange}
        onClose={() => onSelectUser(null)}
      />
    );
  }

  return (
    <UserResults
      users={users}
      totalCount={totalCount}
      needle={needle}
      onNeedleChange={handleNeedleChange}
      page={resultsPage}
      onPageChange={setResultsPage}
      onOpenUser={handleOpenUser}
      loading={loading}
      error={error}
      timezone={timezone}
    />
  );
}
