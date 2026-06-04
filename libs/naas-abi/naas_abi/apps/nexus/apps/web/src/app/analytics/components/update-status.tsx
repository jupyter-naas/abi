'use client';

import { useCallback, useEffect, useState } from 'react';
import { getApiUrl } from '@/lib/config';

function formatLocal(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

interface FileStats {
  file: string;
  count: number;
  duration_ms: number;
}

interface Metadata {
  updated_at: string;
  duration_ms: number;
  events: FileStats;
  aggregates: FileStats[];
}

export function UpdateStatus() {
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchMetadata = useCallback(async () => {
    try {
      const r = await fetch(`${getApiUrl()}/api/analytics/metadata`, { cache: 'no-store' });
      if (!r.ok) return;
      const data = await r.json();
      setMetadata(data);
    } catch {
      // ignore — metadata is best-effort
    }
  }, []);

  useEffect(() => {
    fetchMetadata();
  }, [fetchMetadata]);

  const refresh = useCallback(async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await fetch(`${getApiUrl()}/api/analytics/rebuild`, { method: 'POST' });
      await fetchMetadata();
    } catch {
      // ignore — keep the previous metadata visible on failure
    } finally {
      setRefreshing(false);
    }
  }, [refreshing, fetchMetadata]);

  const tooltip = metadata
    ? `${metadata.events.count} events · ${metadata.aggregates.length} aggregates · rebuilt in ${metadata.duration_ms} ms`
    : 'No rebuild data yet';

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground" title={tooltip}>
      <span>
        Last updated{' '}
        {metadata?.updated_at ? formatLocal(metadata.updated_at) : '—'}
      </span>
    </div>
  );
}
