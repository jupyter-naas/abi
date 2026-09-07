"use client";

import { useEffect, useMemo, useState } from "react";

/** True when *href* points at a playable video (MP4 / X video CDN). */
export function isVideoUrl(href: string): boolean {
  const lower = href.toLowerCase();
  return (
    lower.includes(".mp4") ||
    lower.includes("video.twimg.com") ||
    lower.includes("/ext_tw_video/") ||
    lower.includes("/tweet_video/") ||
    lower.includes("/amplify_video/")
  );
}

/**
 * A post's media, one item at a time.
 *
 * X allows up to four attachments per post; stacking them turned a single post
 * into a page of its own, so they are shown as a carousel instead - one slide
 * in a fixed frame, arrows and dots to move between them. The frame keeps its
 * ratio whatever the item is, so moving between a portrait photo and a video
 * never shifts the feed under the pointer.
 */
export function MediaCarousel({ value }: { value: string }) {
  const urls = useMemo(
    () => value.split(/\s+/).filter(Boolean),
    [value],
  );
  const [index, setIndex] = useState(0);
  const [broken, setBroken] = useState<Record<string, boolean>>({});

  // A different post reuses this component when the feed re-renders; the slide
  // it was left on does not carry over.
  useEffect(() => {
    setIndex(0);
  }, [value]);

  if (!urls.length) return null;

  const count = urls.length;
  const current = Math.min(index, count - 1);
  const href = urls[current];
  const go = (delta: number) =>
    setIndex((i) => (Math.min(i, count - 1) + delta + count) % count);

  const markBroken = () =>
    setBroken((prev) => ({ ...prev, [href]: true }));

  return (
    <div
      className="media-carousel"
      role="group"
      aria-roledescription="carousel"
      aria-label={`${count} media item${count === 1 ? "" : "s"}`}
      onKeyDown={(e) => {
        if (count < 2) return;
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          go(-1);
        } else if (e.key === "ArrowRight") {
          e.preventDefault();
          go(1);
        }
      }}
    >
      <div className="media-frame">
        {broken[href] ? (
          <a
            className="media-fallback"
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            title="Open media"
          >
            media unavailable - open on X
          </a>
        ) : isVideoUrl(href) ? (
          <video
            key={href}
            className="media-item"
            src={href}
            controls
            playsInline
            preload="metadata"
            onError={markBroken}
          />
        ) : (
          <a
            className="media-item-link"
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            title="Open media"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              key={href}
              className="media-item"
              src={href}
              alt=""
              loading="lazy"
              onError={markBroken}
            />
          </a>
        )}

        {count > 1 ? (
          <>
            <button
              type="button"
              className="media-nav media-prev"
              onClick={() => go(-1)}
              aria-label="Previous media"
            >
              ‹
            </button>
            <button
              type="button"
              className="media-nav media-next"
              onClick={() => go(1)}
              aria-label="Next media"
            >
              ›
            </button>
            <span className="media-count" aria-hidden>
              {current + 1} / {count}
            </span>
          </>
        ) : null}
      </div>

      {count > 1 ? (
        <div className="media-dots">
          {urls.map((url, i) => (
            <button
              key={url}
              type="button"
              className={`media-dot${i === current ? " active" : ""}`}
              onClick={() => setIndex(i)}
              aria-label={`Show media ${i + 1} of ${count}`}
              aria-current={i === current}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
