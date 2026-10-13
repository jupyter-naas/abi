'use client';

import { useEffect } from 'react';
import { useMapsStore } from '@/stores/maps';
import { layoutPinSource } from './layout-sources';
import type { LayoutEntry } from './layouts';
import { combinableFeedKeys, layerCountsForFeedLoad } from './maps-layer-counts';

const MAX_CONCURRENT = 8;

async function forEachConcurrent<T>(
  items: readonly T[],
  limit: number,
  fn: (item: T) => Promise<void>,
): Promise<void> {
  const queue = [...items];
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (queue.length > 0) {
      const item = queue.shift()!;
      await fn(item);
    }
  });
  await Promise.all(workers);
}

/**
 * Loads pin counts for every combinable feed/layer (sidebar), even when a layer
 * is switched off on the map.
 */
export function useMapsSidebarLayerCounts(
  workspaceId: string | null,
  entries: readonly LayoutEntry[],
  loading: boolean,
) {
  const setLayerCounts = useMapsStore((s) => s.setLayerCounts);
  const entryKey = entries.map((e) => e.id).join('\0');

  useEffect(() => {
    if (!workspaceId || loading || entries.length === 0) return;
    const feedKeys = combinableFeedKeys(entries);
    if (!feedKeys.length) return;

    const sampleByFeed = new Map<string, LayoutEntry>();
    for (const entry of entries) {
      if (!entry.combinable) continue;
      const key = entry.feedId ?? entry.id;
      if (!sampleByFeed.has(key)) sampleByFeed.set(key, entry);
    }

    const ac = new AbortController();
    void (async () => {
      const merged: Record<string, number> = {};
      await forEachConcurrent(feedKeys, MAX_CONCURRENT, async (feedKey) => {
        const sample = sampleByFeed.get(feedKey);
        if (!sample) return;
        const source = layoutPinSource(sample, workspaceId);
        if (!source) return;
        try {
          const loaded = await source(ac.signal);
          if (ac.signal.aborted) return;
          Object.assign(merged, layerCountsForFeedLoad(entries, feedKey, loaded.pins));
        } catch {
          // Leave counts undefined for feeds that failed (offline, auth, etc.).
        }
      });
      if (!ac.signal.aborted && Object.keys(merged).length > 0) {
        setLayerCounts(merged);
      }
    })();

    return () => ac.abort();
  }, [workspaceId, loading, entryKey, entries, setLayerCounts]);
}
