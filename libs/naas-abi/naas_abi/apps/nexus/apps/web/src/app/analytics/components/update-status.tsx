'use client';

import { RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';

function formatUtc(iso: string): string {
  // 2026-05-22T15:42:18.123Z → "2026-05-22 15:42:18 UTC"
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toISOString().slice(0, 19).replace('T', ' ')} UTC`;
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
  kpis: FileStats;
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
    ? `${metadata.events.count} events · ${metadata.kpis.count} KPI rows · rebuilt in ${metadata.duration_ms} ms`
    : 'No rebuild data yet';

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground" title={tooltip}>
      <span>
        Last updated{' '}
        {metadata?.updated_at ? formatUtc(metadata.updated_at) : '—'}
      </span>
      <button
        type="button"
        onClick={refresh}
        disabled={refreshing}
        aria-label="Refresh analytics"
        className={cn(
          'flex h-6 w-6 items-center justify-center border border-border/60',
          'hover:bg-muted hover:text-foreground transition-colors',
          'disabled:opacity-50 disabled:cursor-not-allowed',
        )}
      >
        <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
      </button>
    </div>
  );
}
