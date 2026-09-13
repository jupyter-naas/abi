'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  computeSheetsPreviewScale,
  prepareSheetsCoverHtml,
  readWorkbookCoverHtml,
  SHEETS_STAGE_HEIGHT,
  SHEETS_STAGE_WIDTH,
} from './sheets-preview-fit';
import { resolveSheetsPreviewAssets } from './sheets-assets';
import { authFetch } from '@/stores/auth';
import type { SheetsTemplatePreview } from '@/lib/sheets-templates';

const COVER_CACHE = new Map<string, string>();
const COVER_INFLIGHT = new Map<string, Promise<string | null>>();
const MAX_COVER_FETCHES = 3;
let activeFetches = 0;
const fetchWaiters: Array<() => void> = [];

function coverCacheKey(workspaceId: string, slug: string): string {
  return `${workspaceId}:${slug}`;
}

export function invalidateSheetsCover(workspaceId: string, slug?: string | null) {
  if (!workspaceId) return;
  if (slug) {
    COVER_CACHE.delete(coverCacheKey(workspaceId, slug));
    return;
  }
  for (const key of [...COVER_CACHE.keys()]) {
    if (key.startsWith(`${workspaceId}:`)) COVER_CACHE.delete(key);
  }
}

async function withCoverFetchSlot<T>(fn: () => Promise<T>): Promise<T> {
  if (activeFetches >= MAX_COVER_FETCHES) {
    await new Promise<void>((resolve) => fetchWaiters.push(resolve));
  }
  activeFetches += 1;
  try {
    return await fn();
  } finally {
    activeFetches -= 1;
    fetchWaiters.shift()?.();
  }
}

async function fetchCoverHtml(workspaceId: string, slug: string): Promise<string | null> {
  const key = coverCacheKey(workspaceId, slug);
  const cached = COVER_CACHE.get(key);
  if (cached) return cached;
  const pending = COVER_INFLIGHT.get(key);
  if (pending) return pending;
  const work = withCoverFetchSlot(async () => {
    const res = await authFetch(
      `/api/sheets/projects/${encodeURIComponent(slug)}/workbook?workspace_id=${encodeURIComponent(workspaceId)}`,
    );
    if (!res.ok) return null;
    const html = await readWorkbookCoverHtml(res);
    if (!html) return null;
    const resolved = await resolveSheetsPreviewAssets(html, workspaceId, slug);
    COVER_CACHE.set(key, resolved);
    return resolved;
  });
  COVER_INFLIGHT.set(key, work);
  try {
    return await work;
  } finally {
    COVER_INFLIGHT.delete(key);
  }
}

export function SheetsCoverFallback({
  title,
  preview,
}: {
  title: string;
  preview: SheetsTemplatePreview;
}) {
  return (
    <div
      className="absolute inset-0"
      style={{ background: preview.preview_bg }}
      data-testid="sheets-cover-fallback"
    >
      <div
        className="absolute inset-3 flex flex-col justify-end p-3"
        style={{
          background: preview.preview_panel,
          color: preview.preview_ink,
          boxShadow: `inset 0 3px 0 ${preview.preview_accent}`,
        }}
      >
        <span className="line-clamp-2 text-sm font-semibold leading-tight">{title}</span>
      </div>
    </div>
  );
}

export function SheetsCoverThumb({
  workspaceId,
  slug,
  title,
  preview,
}: {
  workspaceId: string;
  slug: string;
  title: string;
  preview: SheetsTemplatePreview;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [coverHtml, setCoverHtml] = useState<string | null>(
    () => COVER_CACHE.get(coverCacheKey(workspaceId, slug)) ?? null,
  );

  const measure = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const { width, height } = host.getBoundingClientRect();
    setScale(computeSheetsPreviewScale(width, height));
  }, []);

  useEffect(() => {
    measure();
    const host = hostRef.current;
    if (!host || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(host);
    return () => ro.disconnect();
  }, [measure]);

  useEffect(() => {
    if (!workspaceId || !slug) return;
    let cancelled = false;
    const host = hostRef.current;
    const load = () => {
      void fetchCoverHtml(workspaceId, slug).then((html) => {
        if (!cancelled && html) setCoverHtml(html);
      });
    };
    if (COVER_CACHE.has(coverCacheKey(workspaceId, slug))) {
      load();
      return () => {
        cancelled = true;
      };
    }
    if (!host || typeof IntersectionObserver === 'undefined') {
      load();
      return () => {
        cancelled = true;
      };
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          io.disconnect();
          load();
        }
      },
      { rootMargin: '240px' },
    );
    io.observe(host);
    return () => {
      cancelled = true;
      io.disconnect();
    };
  }, [workspaceId, slug]);

  return (
    <div
      ref={hostRef}
      className="pointer-events-none relative aspect-video w-full overflow-hidden bg-muted/20"
      data-testid="sheets-cover-thumb"
    >
      {!coverHtml ? <SheetsCoverFallback title={title} preview={preview} /> : null}
      {coverHtml ? (
        <iframe
          title={`${title} cover`}
          sandbox=""
          srcDoc={coverHtml}
          className="pointer-events-none block border-0"
          style={{
            width: SHEETS_STAGE_WIDTH,
            height: SHEETS_STAGE_HEIGHT,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
          }}
        />
      ) : null}
    </div>
  );
}

/** In-memory 16:9 thumb for one slide. Loads srcDoc when the card is on screen. */
export function SheetsSlideThumb({
  html,
  index,
  title,
}: {
  html: string;
  index: number;
  title: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const visibleRef = useRef(false);
  const [scale, setScale] = useState(1);
  const [srcDoc, setSrcDoc] = useState<string | null>(null);

  const measure = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const { width, height } = host.getBoundingClientRect();
    setScale(computeSheetsPreviewScale(width, height));
  }, []);

  useEffect(() => {
    measure();
    const host = hostRef.current;
    if (!host || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(host);
    return () => ro.disconnect();
  }, [measure]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !html) return;
    let cancelled = false;
    const load = () => {
      visibleRef.current = true;
      if (cancelled) return;
      setSrcDoc(prepareSheetsCoverHtml(html, index));
    };
    if (visibleRef.current || typeof IntersectionObserver === 'undefined') {
      load();
      return () => {
        cancelled = true;
      };
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          io.disconnect();
          load();
        }
      },
      { rootMargin: '160px' },
    );
    io.observe(host);
    return () => {
      cancelled = true;
      io.disconnect();
    };
  }, [html, index]);

  return (
    <div
      ref={hostRef}
      className="pointer-events-none relative h-full w-full overflow-hidden bg-muted/20"
      data-testid="sheets-slide-thumb"
    >
      {srcDoc ? (
        <iframe
          title={title}
          sandbox=""
          srcDoc={srcDoc}
          className="pointer-events-none block border-0"
          style={{
            width: SHEETS_STAGE_WIDTH,
            height: SHEETS_STAGE_HEIGHT,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
          }}
        />
      ) : null}
    </div>
  );
}
