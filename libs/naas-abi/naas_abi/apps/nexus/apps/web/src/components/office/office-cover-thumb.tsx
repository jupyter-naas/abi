'use client';

import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { authFetch } from '@/stores/auth';
import { resolveOfficePreviewAssets } from './office-assets';
import type { OfficeKind, OfficeKindId, OfficeTemplatePreview } from './office-kinds';

/**
 * How one kind lays out its HTML, for thumbs: the native page or stage size the
 * iframe renders at, how that scales into a thumb box, how a cover is read from
 * the API and how one part (section, sheet tab, slide) is cut out of the HTML.
 * Each kind's preview-fit module exports its own.
 */
export type OfficeCoverFit = {
  width: number;
  height: number;
  scale: (boxWidth: number, boxHeight: number) => number;
  readCoverHtml: (res: Response) => Promise<string | null>;
  prepareCoverHtml: (html: string, index: number) => string | null;
};

type CoverKind = Pick<OfficeKind, 'id' | 'noun' | 'testIdPrefix' | 'aspectClass'>;

const COVER_CACHE = new Map<string, string>();
const COVER_INFLIGHT = new Map<string, Promise<string | null>>();
const MAX_COVER_FETCHES = 3;
let activeFetches = 0;
const fetchWaiters: Array<() => void> = [];

function coverCacheKey(kind: OfficeKindId, workspaceId: string, slug: string): string {
  return `${kind}:${workspaceId}:${slug}`;
}

export function invalidateOfficeCover(kind: OfficeKindId, workspaceId: string, slug?: string | null) {
  if (!workspaceId) return;
  if (slug) {
    COVER_CACHE.delete(coverCacheKey(kind, workspaceId, slug));
    return;
  }
  for (const key of [...COVER_CACHE.keys()]) {
    if (key.startsWith(`${kind}:${workspaceId}:`)) COVER_CACHE.delete(key);
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

async function fetchCoverHtml(
  kind: CoverKind,
  fit: OfficeCoverFit,
  workspaceId: string,
  slug: string,
): Promise<string | null> {
  const key = coverCacheKey(kind.id, workspaceId, slug);
  const cached = COVER_CACHE.get(key);
  if (cached) return cached;
  const pending = COVER_INFLIGHT.get(key);
  if (pending) return pending;
  const work = withCoverFetchSlot(async () => {
    const res = await authFetch(
      `/api/${kind.id}/projects/${encodeURIComponent(slug)}/${kind.noun}?workspace_id=${encodeURIComponent(workspaceId)}`,
    );
    if (!res.ok) return null;
    const html = await fit.readCoverHtml(res);
    if (!html) return null;
    const resolved = await resolveOfficePreviewAssets(kind.id, html, workspaceId, slug);
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

/** Scale of the native page into the host box, kept current as the box resizes. */
function useFitScale(hostRef: RefObject<HTMLDivElement | null>, fit: OfficeCoverFit): number {
  const [scale, setScale] = useState(1);
  const measure = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const { width, height } = host.getBoundingClientRect();
    setScale(fit.scale(width, height));
  }, [hostRef, fit]);

  useEffect(() => {
    measure();
    const host = hostRef.current;
    if (!host || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(host);
    return () => ro.disconnect();
  }, [hostRef, measure]);
  return scale;
}

/** Run `load` once the host scrolls near the viewport (or at once without IntersectionObserver). */
function whenVisible(host: HTMLElement | null, rootMargin: string, load: () => void): () => void {
  if (!host || typeof IntersectionObserver === 'undefined') {
    load();
    return () => {};
  }
  const io = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        io.disconnect();
        load();
      }
    },
    { rootMargin },
  );
  io.observe(host);
  return () => io.disconnect();
}

function ScaledFrame({ title, srcDoc, fit, scale }: { title: string; srcDoc: string; fit: OfficeCoverFit; scale: number }) {
  return (
    <iframe
      title={title}
      sandbox=""
      srcDoc={srcDoc}
      className="pointer-events-none block border-0"
      style={{
        width: fit.width,
        height: fit.height,
        transform: `scale(${scale})`,
        transformOrigin: 'top left',
      }}
    />
  );
}

export function OfficeCoverFallback({
  kind,
  title,
  preview,
}: {
  kind: Pick<OfficeKind, 'testIdPrefix'>;
  title: string;
  preview: OfficeTemplatePreview;
}) {
  return (
    <div
      className="absolute inset-0"
      style={{ background: preview.preview_bg }}
      data-testid={`${kind.testIdPrefix}-cover-fallback`}
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

/** A gallery card's cover: the item's first part, fetched once it is on screen. */
export function OfficeCoverThumb({
  kind,
  fit,
  workspaceId,
  slug,
  title,
  preview,
}: {
  kind: CoverKind;
  fit: OfficeCoverFit;
  workspaceId: string;
  slug: string;
  title: string;
  preview: OfficeTemplatePreview;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const scale = useFitScale(hostRef, fit);
  const [coverHtml, setCoverHtml] = useState<string | null>(
    () => COVER_CACHE.get(coverCacheKey(kind.id, workspaceId, slug)) ?? null,
  );

  useEffect(() => {
    if (!workspaceId || !slug) return;
    let cancelled = false;
    const load = () => {
      void fetchCoverHtml(kind, fit, workspaceId, slug).then((html) => {
        if (!cancelled && html) setCoverHtml(html);
      });
    };
    const cached = COVER_CACHE.has(coverCacheKey(kind.id, workspaceId, slug));
    let stop = () => {};
    if (cached) load();
    else stop = whenVisible(hostRef.current, '240px', load);
    return () => {
      cancelled = true;
      stop();
    };
  }, [kind, fit, workspaceId, slug]);

  return (
    <div
      ref={hostRef}
      className={`pointer-events-none relative ${kind.aspectClass} w-full overflow-hidden bg-muted/20`}
      data-testid={`${kind.testIdPrefix}-cover-thumb`}
    >
      {coverHtml ? (
        <ScaledFrame title={`${title} cover`} srcDoc={coverHtml} fit={fit} scale={scale} />
      ) : (
        <OfficeCoverFallback kind={kind} title={title} preview={preview} />
      )}
    </div>
  );
}

/** In-memory thumb for one part (section, sheet tab, slide). Loads srcDoc when on screen. */
export function OfficePartThumb({
  fit,
  testId,
  html,
  index,
  title,
}: {
  fit: OfficeCoverFit;
  testId: string;
  html: string;
  index: number;
  title: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const visibleRef = useRef(false);
  const scale = useFitScale(hostRef, fit);
  const [srcDoc, setSrcDoc] = useState<string | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !html) return;
    let cancelled = false;
    const load = () => {
      visibleRef.current = true;
      if (cancelled) return;
      setSrcDoc(fit.prepareCoverHtml(html, index));
    };
    let stop = () => {};
    if (visibleRef.current) load();
    else stop = whenVisible(host, '160px', load);
    return () => {
      cancelled = true;
      stop();
    };
  }, [fit, html, index]);

  return (
    <div
      ref={hostRef}
      className="pointer-events-none relative h-full w-full overflow-hidden bg-muted/20"
      data-testid={testId}
    >
      {srcDoc ? <ScaledFrame title={title} srcDoc={srcDoc} fit={fit} scale={scale} /> : null}
    </div>
  );
}
