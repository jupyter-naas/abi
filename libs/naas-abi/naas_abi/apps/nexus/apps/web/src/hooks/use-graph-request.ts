'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';

/** Read-only graph POST requests, scoped to their parameters even during rapid navigation. */
export function useGraphRequest<T>(endpoint: string, body: object) {
  const payload = JSON.stringify(body);
  const key = `${endpoint}:${payload}`;
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ key: string; data: T | null; error: string | null; loading: boolean }>({ key, data: null, error: null, loading: true });

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setResult({ key, data: null, error: null, loading: true });
    void authFetch(`${getApiUrl()}/api/graph/${endpoint}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload, signal: controller.signal,
    }).then(async response => {
      if (!response.ok) throw new Error('Could not load graph data. Please try again.');
      return await response.json() as T;
    }).then(data => {
      if (active) setResult({ key, data, error: null, loading: false });
    }).catch(() => {
      if (active) setResult({ key, data: null, error: 'Could not load graph data. Please try again.', loading: false });
    });
    return () => { active = false; controller.abort(); };
  }, [endpoint, payload, key, attempt]);

  return {
    data: result.key === key ? result.data : null,
    error: result.key === key ? result.error : null,
    loading: result.key !== key || result.loading,
    retry: () => setAttempt(value => value + 1),
  };
}
