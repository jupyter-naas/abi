'use client';

import { useEffect, useState } from 'react';

/**
 * Optional feed ids from ``/api/maps/organization-facilities/workspace-defaults``:
 * `undefined` while the request is pending, `null` when the workspace has none.
 */
export function useWorkspaceMapDefaultFeeds(
  workspaceId: string | null,
): readonly string[] | null | undefined {
  const [feedIds, setFeedIds] = useState<readonly string[] | null | undefined>(undefined);

  useEffect(() => {
    if (!workspaceId) {
      setFeedIds(null);
      return;
    }
    let cancelled = false;
    setFeedIds(undefined);
    const url = `/api/maps/organization-facilities/workspace-defaults?workspace_id=${encodeURIComponent(workspaceId)}`;
    fetch(url, { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { default_on_feed_ids?: string[] } | null) => {
        if (cancelled) return;
        setFeedIds(data?.default_on_feed_ids?.length ? data.default_on_feed_ids : null);
      })
      .catch(() => {
        if (!cancelled) setFeedIds(null);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  return feedIds;
}
