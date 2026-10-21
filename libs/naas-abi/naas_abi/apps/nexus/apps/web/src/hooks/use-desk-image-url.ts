'use client';

import { useEffect, useState } from 'react';
import { isApiBackgroundUrl } from '@/lib/home-background';
import { authFetch } from '@/stores/auth';

/**
 * The URL to paint the Home desk with. External URLs pass straight through;
 * a wallpaper kept in the workspace drive is served by the API behind auth,
 * which CSS `url()` cannot send, so it is fetched once and shown as a blob URL.
 * The previous blob is revoked whenever the wallpaper changes.
 */
export function useDeskImageUrl(url: string | undefined): string | undefined {
  const needsFetch = isApiBackgroundUrl(url);
  const [blobUrl, setBlobUrl] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!needsFetch || !url) {
      setBlobUrl(undefined);
      return;
    }
    let cancelled = false;
    let created: string | undefined;
    void (async () => {
      try {
        const response = await authFetch(url);
        if (!response.ok || cancelled) return;
        const blob = await response.blob();
        if (cancelled) return;
        created = URL.createObjectURL(blob);
        setBlobUrl(created);
      } catch {
        // Wallpaper is decoration: fall back to the desk colour.
      }
    })();
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [needsFetch, url]);

  return needsFetch ? blobUrl : url;
}
