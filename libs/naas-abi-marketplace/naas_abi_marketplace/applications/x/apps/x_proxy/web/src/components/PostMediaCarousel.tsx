"use client";

import { useEffect, useState } from "react";
import { MediaCarousel } from "@/components/MediaCarousel";
import { withAccessToken } from "@/lib/routes";

const APP_BASE = "/app-html/x/apps/x_proxy";

function needsRuntimeEnsure(value: string): boolean {
  const parts = value.split(/\s+/).filter(Boolean);
  if (!parts.length) return false;
  return parts.some((href) => /^https?:\/\//i.test(href));
}

type Props = {
  tweetId: string | null;
  value: string;
};

/**
 * Fetches and stores tweet media on first view when catalog rows are still pending.
 */
export function PostMediaCarousel({ tweetId, value }: Props) {
  const [resolved, setResolved] = useState(value);

  useEffect(() => {
    setResolved(value);
  }, [value]);

  useEffect(() => {
    if (!tweetId || !value.trim()) return;
    if (!needsRuntimeEnsure(value)) return;

    let live = true;
    fetch(
      withAccessToken(
        `${APP_BASE}/dataset/posts/${encodeURIComponent(tweetId)}/media.json`,
      ),
    )
      .then((res) => (res.ok ? res.json() : null))
      .then((doc) => {
        if (!live || !doc?.media_urls) return;
        setResolved(String(doc.media_urls));
      })
      .catch(() => undefined);

    return () => {
      live = false;
    };
  }, [tweetId, value]);

  if (!resolved.trim()) return null;
  return <MediaCarousel value={resolved} />;
}
