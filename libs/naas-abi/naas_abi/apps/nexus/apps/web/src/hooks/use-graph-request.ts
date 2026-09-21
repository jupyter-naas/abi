'use client';

import { useCallback, useEffect, useState } from 'react';
import { authFetch, useAuthStore } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { GraphReadCache } from '@/lib/graph-request-cache';

const cache = new GraphReadCache();
const requestKey = (endpoint: string, payload: string) =>
  JSON.stringify([getApiUrl(), useAuthStore.getState().user?.id, endpoint, payload]);
const cacheable = (endpoint: string) => endpoint.startsWith('explorer/');

useAuthStore.subscribe((state, previous) => {
  if (state.user?.id !== previous.user?.id || Boolean(state.token) !== Boolean(previous.token)) cache.clear();
});
if (typeof window !== 'undefined') {
  window.addEventListener('graph-cache-refresh', () => cache.clear());
  window.addEventListener('graph-list-update', () => cache.clear());
}

/** Only Explorer reads are cached, with the full workspace/filter/page and current user in the key. */
export async function readGraph<T>(endpoint: string, payload: string, signal: AbortSignal, force = false): Promise<T> {
  const key = requestKey(endpoint, payload);
  if (force) cache.delete(key);
  const saved = cacheable(endpoint) ? cache.get<T>(key) : undefined;
  if (saved !== undefined) return saved;
  const generation = cache.generation;
  const response = await authFetch(`${getApiUrl()}/api/graph/${endpoint}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload, signal,
  });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) cache.clear();
    throw new Error(response.status === 403
      ? 'This graph selection is unavailable. Choose All Graphs to reset.'
      : 'Could not load graph data. Please try again.');
  }
  const data = await response.json() as T;
  if (cacheable(endpoint) && !signal.aborted) cache.set(key, data, generation);
  return data;
}

/** Read-only graph POST requests, scoped to their parameters even during rapid navigation. */
export function useGraphRequest<T>(endpoint: string, body: object, enabled = true) {
  const userId = useAuthStore(state => state.user?.id);
  const payload = JSON.stringify(body);
  const key = JSON.stringify([userId, endpoint, payload]);
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ key: string; data: T | null; error: string | null; loading: boolean }>({ key, data: null, error: null, loading: true });
  const saved = enabled && cacheable(endpoint) ? cache.get<T>(requestKey(endpoint, payload)) : undefined;

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let active = true;
    const cached = cacheable(endpoint) ? cache.get<T>(requestKey(endpoint, payload)) : undefined;
    if (cached !== undefined) {
      setResult({ key, data: cached, error: null, loading: false });
      return;
    }
    setResult({ key, data: null, error: null, loading: true });
    void readGraph<T>(endpoint, payload, controller.signal).then(data => {
      if (active) setResult({ key, data, error: null, loading: false });
    }).catch((error: unknown) => {
      if (active) setResult({ key, data: null, error: error instanceof Error ? error.message : 'Could not load graph data. Please try again.', loading: false });
    });
    return () => { active = false; controller.abort(); };
  }, [endpoint, payload, key, attempt, enabled]);

  const retry = useCallback(() => {
    cache.delete(requestKey(endpoint, payload));
    setResult({ key, data: null, error: null, loading: true });
    setAttempt(value => value + 1);
  }, [endpoint, payload, key]);
  useEffect(() => {
    if (!enabled || !cacheable(endpoint)) return;
    window.addEventListener('graph-cache-refresh', retry);
    window.addEventListener('graph-list-update', retry);
    return () => {
      window.removeEventListener('graph-cache-refresh', retry);
      window.removeEventListener('graph-list-update', retry);
    };
  }, [enabled, endpoint, retry]);
  return {
    data: enabled ? saved ?? (result.key === key ? result.data : null) : null,
    error: enabled && saved === undefined && result.key === key ? result.error : null,
    loading: enabled && saved === undefined && (result.key !== key || result.loading),
    retry,
  };
}
