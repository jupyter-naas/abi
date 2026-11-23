import { useEffect, useState } from 'react';

import { webPassReady } from '@/lib/web-pass';

/**
 * False until this host holds a live web pass, or stops waiting for one
 * (`webPassReady`). A tree that loads images or maps from this host's own
 * routes renders once it is true, so its first requests carry the pass.
 */
export function useWebPassReady(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let live = true;
    void webPassReady().then(() => {
      if (live) setReady(true);
    });
    return () => {
      live = false;
    };
  }, []);
  return ready;
}
