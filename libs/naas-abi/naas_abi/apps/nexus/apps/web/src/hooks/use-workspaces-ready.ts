'use client';

import { useEffect, useState } from 'react';
import { useWorkspaceStore } from '@/stores/workspace';

/** The first retry waits this long, each next one twice as long, up to `MAX_RETRY_MS`. */
export const FIRST_RETRY_MS = 1000;
export const MAX_RETRY_MS = 10_000;

/**
 * Reads the workspaces until the API answers them once (`workspacesReady`), retrying while it
 * starts or does not answer: a page that waits on it shows a loader, never an app without its
 * client workspaces and colors. `retrying` once a read failed. Nothing is read while `enabled`
 * is false (no session yet).
 */
export function useWorkspacesReady(enabled = true): { ready: boolean; retrying: boolean } {
  const ready = useWorkspaceStore((s) => s.workspacesReady);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = FIRST_RETRY_MS;
    const attempt = () => {
      void useWorkspaceStore
        .getState()
        .fetchWorkspaces()
        .finally(() => {
          if (cancelled || useWorkspaceStore.getState().workspacesReady) return;
          setRetrying(true);
          timer = setTimeout(attempt, delay);
          delay = Math.min(delay * 2, MAX_RETRY_MS);
        });
    };
    attempt();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [enabled]);

  return { ready, retrying };
}
