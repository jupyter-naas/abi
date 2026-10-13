'use client';

import { useEffect, useState } from 'react';

/** Optional feed ids from ``/api/maps/organization-facilities/workspace-defaults``. */
export function useWorkspaceMapDefaultFeeds(workspaceId: string | null): readonly string[] | null {
  const [feedIds, setFeedIds] = useState<readonly string[] | null>(null);

  useEffect(() => {
    if (!workspaceId) {
      setFeedIds(null);
      return;
    }
    let cancelled = false;
    const url = `/api/maps/organization-facilities/workspace-defaults?workspace_id=${encodeURIComponent(workspaceId)}`;
    fetch(url, { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { default_on_feed_ids?: string[] } | null) => {
        if (cancelled || !data?.default_on_feed_ids?.length) return;
        setFeedIds(data.default_on_feed_ids);
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
