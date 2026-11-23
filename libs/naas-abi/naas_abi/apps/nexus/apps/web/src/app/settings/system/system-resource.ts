'use client';

import { useState } from 'react';
import { loadSystem, type Loaded } from './system-api';
import { usePoll } from './use-poll';

/** Reads a SysAdmin view; the signal is aborted when the read is no longer wanted. */
export type SystemLoader = <T>(path: string, signal: AbortSignal) => Promise<Loaded<T>>;

const loadFromApi: SystemLoader = (path, signal) => loadSystem(path, undefined, signal);

/**
 * Load a SysAdmin view while ``enabled``, then poll it ``intervalMs`` after each read
 * settles (skipped while the tab is hidden): reads never overlap, and closing the view
 * stops them. Changing ``nonce`` (Refresh) or ``path`` aborts the pending read and reads
 * again; an answer begun before that, or for another path, is never shown.
 */
export function useSystemResource<T>(
  path: string,
  {
    enabled,
    intervalMs,
    nonce,
    load = loadFromApi,
  }: { enabled: boolean; intervalMs: number; nonce: number; load?: SystemLoader },
): Loaded<T> | null {
  const [state, setState] = useState<{ path: string; loaded: Loaded<T> } | null>(null);

  usePoll(
    (signal) =>
      load<T>(path, signal).then((loaded) => {
        if (!signal.aborted) setState({ path, loaded });
      }),
    intervalMs,
    enabled,
    [path, nonce, load],
  );

  return state?.path === path ? state.loaded : null;
}
