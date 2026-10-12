'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '@/stores/auth';

/**
 * Object URL for an image served by the API behind auth (`<img src>` cannot
 * send the Bearer token). Blobs are shared between components per URL, so a
 * picker and a settings table showing the same preview fetch it once; include
 * a version in the URL to refresh after an upload.
 */
const cache = new Map<string, Promise<string | undefined>>();

function load(url: string): Promise<string | undefined> {
  let pending = cache.get(url);
  if (!pending) {
    pending = authFetch(url)
      .then(async (response) => (response.ok ? URL.createObjectURL(await response.blob()) : undefined))
      .catch(() => undefined);
    pending.then((value) => {
      if (value === undefined) cache.delete(url);
    });
    cache.set(url, pending);
  }
  return pending;
}

export function useAuthedImageUrl(url: string | null | undefined): string | undefined {
  const [objectUrl, setObjectUrl] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!url) {
      setObjectUrl(undefined);
      return;
    }
    let cancelled = false;
    void load(url).then((value) => {
      if (!cancelled) setObjectUrl(value);
    });
    return () => {
      cancelled = true;
    };
  }, [url]);

  return objectUrl;
}
