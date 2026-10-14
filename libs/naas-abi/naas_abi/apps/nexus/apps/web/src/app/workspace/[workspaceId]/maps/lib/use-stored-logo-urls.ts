'use client';

import { useEffect, useRef, useState } from 'react';
import { loadAuthedImageUrl } from '@/hooks/use-authed-image-url';
import type { WorkspaceMapLayout } from './layouts';
import { layoutsApi } from './layouts-api';

/** Logos load a few at a time so they never crowd out the map's own requests. */
const MAX_CONCURRENT = 4;
const RETRY_DELAY_MS = 2000;

/**
 * Object URLs of stored feed logos (`logo_path`), by feed id. The logo route
 * needs the member token, which `<img>` and Leaflet pin HTML cannot send, so
 * each logo is fetched once and shared (sidebar, legend, pins, Settings).
 * Enabled feeds load first; each logo shows as soon as it is there.
 */
export function useStoredLogoUrls(
  workspaceId: string | null,
  feeds: readonly WorkspaceMapLayout[],
  hiddenFeeds: readonly string[] = [],
): Record<string, string> {
  const [urls, setUrls] = useState<Record<string, string>>({});
  // Which logos (the key is in the URL, so a changed logo is fetched again).
  // Enabling or disabling a feed only changes the order: it does not reload.
  const wanted = feeds
    .filter((feed) => feed.logo_path)
    .map((feed) => `${feed.id}\n${feed.logo_path}`)
    .sort()
    .join('\n\n');
  const hiddenRef = useRef(hiddenFeeds);
  hiddenRef.current = hiddenFeeds;

  useEffect(() => {
    setUrls({});
  }, [workspaceId]);

  useEffect(() => {
    if (!workspaceId || !wanted) return;
    let cancelled = false;
    const off = new Set(hiddenRef.current);
    const queue = wanted
      .split('\n\n')
      .map((item) => item.split('\n') as [string, string])
      .sort(([a], [b]) => Number(off.has(a)) - Number(off.has(b)));
    const load = async ([id, path]: [string, string]) => {
      const url = `${layoutsApi.logoUrl(workspaceId, id)}&v=${encodeURIComponent(path)}`;
      let objectUrl = await loadAuthedImageUrl(url);
      if (!objectUrl && !cancelled) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
        objectUrl = cancelled ? undefined : await loadAuthedImageUrl(url);
      }
      if (objectUrl && !cancelled) setUrls((current) => ({ ...current, [id]: objectUrl }));
    };
    const workers = Array.from({ length: Math.min(MAX_CONCURRENT, queue.length) }, async () => {
      while (!cancelled && queue.length > 0) await load(queue.shift()!);
    });
    void Promise.all(workers);
    return () => {
      cancelled = true;
    };
  }, [workspaceId, wanted]);

  return urls;
}
