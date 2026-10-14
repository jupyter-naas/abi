/** The Jobs notification: runs that failed since an admin last looked. */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { JobsApi } from './jobs-api';
import type { JobFailures } from './jobs-types';

export const SEEN_KEY = 'nexus.system.jobs.failures-seen';
const POLL_MS = 60_000;

// Per browser, a convenience: without storage the badge covers the last day.
function readSeen(): string | null {
  try {
    return window.localStorage.getItem(SEEN_KEY);
  } catch {
    return null;
  }
}

function writeSeen(iso: string): void {
  try {
    window.localStorage.setItem(SEEN_KEY, iso);
  } catch {
    /* storage blocked: the mark lasts until the page reloads */
  }
}

/** Failed runs since the last "mark as seen" (else the last day), polled every minute. */
export function useJobFailures(api: JobsApi, enabled: boolean) {
  const [failures, setFailures] = useState<JobFailures | null>(null);
  const seen = useRef<string | null>(null);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    seen.current = readSeen();
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const load = () => {
      void api.failures(seen.current ?? readSeen()).then((result) => {
        if (alive && result.ok) setFailures(result.data);
      });
    };
    load();
    const timer = window.setInterval(() => {
      if (!document.hidden) load();
    }, POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [api, enabled, reloads]);

  const markSeen = useCallback(() => {
    const now = new Date().toISOString();
    seen.current = now;
    writeSeen(now);
    setReloads((n) => n + 1);
  }, []);

  return { failures, markSeen };
}
