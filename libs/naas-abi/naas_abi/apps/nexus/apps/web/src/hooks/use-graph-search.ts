'use client';
import { useEffect, useState } from 'react';
import { authFetch, useAuthStore } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';

export interface GraphSearchHit {
  uri: string; label: string; kind: 'class' | 'individual';
  class_uri: string; class_label: string; graph_uri: string; instance_count: number;
}

/** Search objects directly; cancel and hide old results when the user or scope changes. */
export function useGraphSearch(workspaceId: string, graphs: string[], classes: string[], query: string) {
  const userId = useAuthStore(s => s.user?.id);
  const signedIn = useAuthStore(s => Boolean(s.token));
  const params = new URLSearchParams({ workspace_id: workspaceId, q: query.trim(), limit: '30' });
  graphs.forEach(uri => params.append('graph_uri', uri));
  classes.forEach(uri => params.append('class_uri', uri));
  const args = params.toString();
  const key = JSON.stringify([userId, signedIn, args]);
  const enabled = query.trim().length >= 2;
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{key: string; results: GraphSearchHit[]; error: string | null; loading: boolean}>({key: '', results: [], error: null, loading: false});
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setState({key, results: [], error: null, loading: true});
    const timer = window.setTimeout(() => {
      void authFetch(`${getApiUrl()}/api/graph/search?${args}`, {signal: controller.signal})
        .then(async response => {
          if (!response.ok) throw new Error(response.status === 403 ? 'This graph selection is unavailable. Choose All Graphs to reset.' : 'Search could not load. Please try again.');
          const data = await response.json() as { results: GraphSearchHit[] };
          if (!controller.signal.aborted) setState({key, results: data.results, error: null, loading: false});
        }).catch((error: unknown) => {
          if (!controller.signal.aborted) setState({key, results: [], error: error instanceof Error ? error.message : 'Search could not load.', loading: false});
        });
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [key, args, enabled, attempt]);
  useEffect(() => {
    const refresh = () => setAttempt(value => value + 1);
    window.addEventListener('graph-cache-refresh', refresh);
    return () => window.removeEventListener('graph-cache-refresh', refresh);
  }, []);
  return {
    results: enabled && state.key === key ? state.results : [],
    error: enabled && state.key === key ? state.error : null,
    loading: enabled && (state.key !== key || state.loading),
    retry: () => setAttempt(value => value + 1),
  };
}
