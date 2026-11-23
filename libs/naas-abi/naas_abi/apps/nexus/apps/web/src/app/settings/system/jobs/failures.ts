/** The Jobs notification: runs that failed since an admin last looked. */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { usePoll } from '../use-poll';
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

  usePoll(
    (signal) =>
      api.failures(seen.current ?? readSeen(), signal).then((result) => {
        if (!signal.aborted && result.ok) setFailures(result.data);
      }),
    POLL_MS,
    enabled,
    [api, reloads],
  );

  const markSeen = useCallback(() => {
    const now = new Date().toISOString();
    seen.current = now;
    writeSeen(now);
    setReloads((n) => n + 1);
  }, []);

  return { failures, markSeen };
}

export type JobFailuresState = ReturnType<typeof useJobFailures>;

/** The Platform Settings shell polls once and shares it: the Jobs item's badge and the page. */
export const JobFailuresContext = createContext<JobFailuresState | null>(null);

export function useSharedJobFailures(): JobFailuresState {
  return useContext(JobFailuresContext) ?? { failures: null, markSeen: () => undefined };
}
