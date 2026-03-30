'use client';

/**
 * useGit — polls the real ~/aia git state from /api/lab/git/.
 * Used by the Header branch selector to show real branches and status.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';

const API = () => `${getApiUrl()}/api/lab/git`;
const POLL_MS = 10_000; // refresh every 10s

export interface GitBranch {
  name: string;
  current: boolean;
  remote: boolean;
  ahead: number;
  behind: number;
}

export interface GitChangedFile {
  status: string;
  path: string;
}

export interface GitStatus {
  branch: string;
  ahead: number;
  behind: number;
  changed: GitChangedFile[];
  staged: GitChangedFile[];
  untracked: GitChangedFile[];
  is_dirty: boolean;
}

export function useGit() {
  const [branches, setBranches] = useState<GitBranch[]>([]);
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [branchRes, statusRes] = await Promise.all([
        authFetch(`${API()}/branches`),
        authFetch(`${API()}/status`),
      ]);
      if (branchRes.ok) setBranches(await branchRes.json());
      if (statusRes.ok) setStatus(await statusRes.json());
      setError(null);
    } catch {
      setError('git unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + polling
  useEffect(() => {
    setLoading(true);
    refresh();
    timerRef.current = setInterval(refresh, POLL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [refresh]);

  const checkout = useCallback(async (branch: string, create = false) => {
    try {
      const res = await authFetch(`${API()}/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ branch, create }),
      });
      if (!res.ok) throw new Error('checkout failed');
      await refresh();
      return true;
    } catch {
      return false;
    }
  }, [refresh]);

  const currentBranch = branches.find((b) => b.current) ?? null;
  const totalChanges = status
    ? status.staged.length + status.changed.length + status.untracked.length
    : 0;

  return { branches, status, currentBranch, totalChanges, loading, error, refresh, checkout };
}
