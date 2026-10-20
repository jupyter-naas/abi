"use client";

import { useEffect, useState } from "react";
import {
  MediaCarousel,
  MediaProcessingPlaceholder,
} from "@/components/MediaCarousel";
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
  const mustEnsure = Boolean(tweetId && value.trim() && needsRuntimeEnsure(value));
  const [resolved, setResolved] = useState(value);
  const [processing, setProcessing] = useState(mustEnsure);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setResolved(value);
    setFailed(false);
    setProcessing(Boolean(tweetId && value.trim() && needsRuntimeEnsure(value)));
  }, [tweetId, value]);

  useEffect(() => {
    if (!mustEnsure) return;

    let live = true;
    setProcessing(true);
    setFailed(false);

    fetch(
      withAccessToken(
        `${APP_BASE}/dataset/posts/${encodeURIComponent(tweetId!)}/media.json`,
      ),
    )
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<{ media_urls?: string }>;
      })
      .then((doc) => {
        if (!live) return;
        const urls = String(doc?.media_urls || "").trim();
        if (urls) {
          setResolved(urls);
        } else {
          setFailed(true);
        }
      })
      .catch(() => {
        if (live) setFailed(true);
      })
      .finally(() => {
        if (live) setProcessing(false);
      });

    return () => {
      live = false;
    };
  }, [tweetId, mustEnsure]);

  if (processing) {
    return <MediaProcessingPlaceholder label="Processing media…" />;
  }

  if (failed && needsRuntimeEnsure(resolved)) {
    return (
      <div className="media-carousel">
        <div className="media-frame media-frame-loading">
          <span className="media-loader-label">Media could not be processed</span>
        </div>
      </div>
    );
  }

  if (!resolved.trim()) return null;
  return <MediaCarousel value={resolved} />;
}
