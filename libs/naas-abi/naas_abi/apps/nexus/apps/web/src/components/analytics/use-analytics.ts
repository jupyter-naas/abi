'use client';

import { useEffect, useState } from 'react';
import { authFetch, useAuthStore } from '@/stores/auth';
import { AnalyticsHttpError, readAnalyticsJson } from './api';
import { analyticsUrl, type AnalyticsFilters, type AnalyticsScope } from './scope';

/** Whether the persisted session was read (before that, a request has no cookie context). */
export function useAuthHydrated(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (useAuthStore.persist.hasHydrated()) {
      setReady(true);
      return;
    }
    return useAuthStore.persist.onFinishHydration(() => setReady(true));
  }, []);
  return ready;
}

export interface AnalyticsRead<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** The HTTP status of a refused read (403, 404), null otherwise. */
  status: number | null;
}

/**
 * One read of a scope's analytics: `path` under the scope's base, with the period and
 * filters; `filters` null reads without a query. `skip` asks nothing (the tab is hidden,
 * the user is unknown). A new URL drops the previous answer's error, not its data, so
 * a period change does not blank the page.
 */
export function useAnalytics<T>(
  scope: AnalyticsScope,
  path: string,
  filters: AnalyticsFilters | null,
  { extra, skip = false }: { extra?: Record<string, string>; skip?: boolean } = {}
): AnalyticsRead<T> {
  const url = analyticsUrl(scope, path, filters ?? undefined, extra);
  const authReady = useAuthHydrated();
  const [state, setState] = useState<AnalyticsRead<T> & { url: string | null }>({
    url: null,
    data: null,
    loading: true,
    error: null,
    status: null,
  });

  useEffect(() => {
    if (!authReady || skip) return;
    let cancelled = false;
    setState((s) => ({ ...s, url, loading: true, error: null, status: null }));
    authFetch(url)
      .then((r) => readAnalyticsJson<T>(r))
      .then((data) => {
        if (!cancelled) setState({ url, data, loading: false, error: null, status: null });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const status = e instanceof AnalyticsHttpError ? e.status : null;
        const message = e instanceof Error ? e.message : String(e);
        setState({ url, data: null, loading: false, error: message, status });
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, skip, url]);

  return { data: state.data, loading: state.loading, error: state.error, status: state.status };
}
