'use client';

import { useEffect, useState } from 'react';
import { loadSystem, type Loaded } from './system-api';

/**
 * Load a SysAdmin view while ``enabled``, then poll it every ``intervalMs``
 * (skipped while the tab is hidden). Changing ``nonce`` reloads at once.
 */
export function useSystemResource<T>(
  path: string,
  { enabled, intervalMs, nonce }: { enabled: boolean; intervalMs: number; nonce: number },
): Loaded<T> | null {
  const [state, setState] = useState<Loaded<T> | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const load = async () => {
      const loaded = await loadSystem<T>(path);
      if (!cancelled) setState(loaded);
    };
    void load();
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [path, enabled, intervalMs, nonce]);

  return state;
}
