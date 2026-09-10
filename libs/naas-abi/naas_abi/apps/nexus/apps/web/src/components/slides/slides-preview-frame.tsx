'use client';

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { resolveSlidesPreviewAssets } from './slides-assets';
import {
  computeSlidesPreviewScale,
  countSlideSections,
  isSlidesPreviewMessage,
  prepareSlidesPreviewHtml,
  slidesPreviewIndexFromScroll,
  slidesPreviewScrollTop,
  SLIDES_PDF_EXPORT_ACK_MS,
  SLIDES_PREVIEW_IMAGES_READY_TIMEOUT_MS,
  SLIDES_PREVIEW_MESSAGE_SOURCE,
  SLIDES_STAGE_HEIGHT,
  SLIDES_STAGE_WIDTH,
  type SlidesPreviewFromParentMessage,
  type SlidesTextEdit,
} from './slides-preview-fit';

export interface SlidesPreviewFrameHandle {
  exportPptx: () => Promise<void>;
  exportPdf: () => Promise<void>;
}

export interface SlidesPreviewFrameProps {
  html: string;
  workspaceId?: string;
  slug?: string;
  className?: string;
  title?: string;
  selectedIndex?: number;
  onSelectedIndexChange?: (index: number) => void;
  manualEdit?: boolean;
  onManualEditCommit?: (edits: SlidesTextEdit[]) => void;
}

/**
 * Present-style preview: fixed 1280x720 stage scaled with object-fit:contain
 * into the available center pane (letterbox OK). The full deck scrolls at
 * that scale (PowerPoint Normal view). Filmstrip click jumps scroll; host
 * scroll updates the selected index.
 *
 * Sandbox omits allow-same-origin. Height, PPTX, PDF, and Manual edit use
 * the postMessage bridge. allow-modals is required so File, Print / Save as
 * PDF can open the browser print dialog. Viewport-fit is stripped in
 * prepareSlidesPreviewHtml so the parent contain-scale is the only scale.
 *
 * Relative ``assets/`` paths 404 inside srcDoc. The parent fetches the slides
 * asset route with Bearer auth and inlines data-URLs before setting srcDoc.
 *
 * The iframe stays transparent (and a spinner shows) until the in-frame
 * bridge reports every ``<img>`` has loaded/errored, or the ready timeout.
 */
export const SlidesPreviewFrame = forwardRef<
  SlidesPreviewFrameHandle,
  SlidesPreviewFrameProps
>(function SlidesPreviewFrame(
  {
    html,
    workspaceId = '',
    slug = '',
    className,
    title = 'Slides preview',
    selectedIndex = 0,
    onSelectedIndexChange,
    manualEdit = false,
    onManualEditCommit,
  },
  ref,
) {
  const hostRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const manualEditRef = useRef(manualEdit);
  const onManualEditCommitRef = useRef(onManualEditCommit);
  const acceptEditsUntilRef = useRef(0);
  const slideCountRef = useRef(1);
  const [scale, setScale] = useState(1);
  const [docHeight, setDocHeight] = useState(SLIDES_STAGE_HEIGHT);
  const [hostHeight, setHostHeight] = useState(0);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [imagesReady, setImagesReady] = useState(false);

  manualEditRef.current = manualEdit;
  onManualEditCommitRef.current = onManualEditCommit;

  const stageHeightForCount = (count: number) =>
    Math.max(1, count) * SLIDES_STAGE_HEIGHT;

  useEffect(() => {
    let cancelled = false;
    setImagesReady(false);
    const count = Math.max(1, countSlideSections(html));
    slideCountRef.current = count;
    setDocHeight(stageHeightForCount(count));
    void resolveSlidesPreviewAssets(html, workspaceId, slug).then((resolved) => {
      if (cancelled) return;
      const nextCount = Math.max(1, countSlideSections(resolved));
      slideCountRef.current = nextCount;
      setDocHeight(stageHeightForCount(nextCount));
      setPreviewHtml(prepareSlidesPreviewHtml(resolved));
    });
    return () => {
      cancelled = true;
    };
  }, [html, workspaceId, slug]);

  useEffect(() => {
    if (imagesReady) return;
    const timer = window.setTimeout(
      () => setImagesReady(true),
      SLIDES_PREVIEW_IMAGES_READY_TIMEOUT_MS,
    );
    return () => window.clearTimeout(timer);
  }, [previewHtml, imagesReady]);

  const exportWaiters = useRef<
    Array<{
      resolve: () => void;
      reject: (error: Error) => void;
      timer: number;
    }>
  >([]);

  const measureHost = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const { width, height } = host.getBoundingClientRect();
    setHostHeight(height);
    setScale(computeSlidesPreviewScale(width, height));
  }, []);

  useLayoutEffect(() => {
    measureHost();
  }, [measureHost]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => measureHost());
    ro.observe(host);
    return () => ro.disconnect();
  }, [measureHost]);

  const postManualEdit = useCallback((enabled: boolean) => {
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    if (!enabled) acceptEditsUntilRef.current = Date.now() + 1500;
    const msg: SlidesPreviewFromParentMessage = {
      source: SLIDES_PREVIEW_MESSAGE_SOURCE,
      type: 'set-manual-edit',
      enabled,
    };
    win.postMessage(msg, '*');
  }, []);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.source !== iframeRef.current?.contentWindow) return;
      if (!isSlidesPreviewMessage(event.data)) return;
      if (
        event.data.type === 'metrics' ||
        event.data.type === 'ready' ||
        event.data.type === 'images-ready'
      ) {
        if (typeof event.data.height === 'number' && event.data.height > 0) {
          setDocHeight(
            Math.max(event.data.height, stageHeightForCount(slideCountRef.current)),
          );
        }
        if (event.data.type === 'images-ready') setImagesReady(true);
        if (event.data.type === 'ready' && manualEditRef.current) {
          postManualEdit(true);
        }
        return;
      }
      if (event.data.type === 'edit-commit') {
        if (!manualEditRef.current && Date.now() > acceptEditsUntilRef.current) return;
        onManualEditCommitRef.current?.(event.data.edits);
        return;
      }
      if (
        event.data.type === 'export-pptx-result' ||
        event.data.type === 'export-pdf-result'
      ) {
        const waiters = exportWaiters.current.splice(0);
        waiters.forEach((w) => window.clearTimeout(w.timer));
        if (event.data.ok) {
          waiters.forEach((w) => w.resolve());
        } else {
          const fallback =
            event.data.type === 'export-pdf-result'
              ? 'PDF export failed'
              : 'PPTX export failed';
          const err = new Error(event.data.error || fallback);
          waiters.forEach((w) => w.reject(err));
        }
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [postManualEdit]);

  useEffect(() => {
    if (!previewHtml || !imagesReady) return;
    postManualEdit(manualEdit);
  }, [manualEdit, previewHtml, imagesReady, postManualEdit]);

  const ignoreScrollRef = useRef(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const target = slidesPreviewScrollTop(selectedIndex, scale);
    ignoreScrollRef.current = true;
    if (Math.abs(host.scrollTop - target) >= SLIDES_STAGE_HEIGHT * scale * 0.25) {
      host.scrollTo({ top: target });
    }
    const timer = window.setTimeout(() => {
      ignoreScrollRef.current = false;
    }, 250);
    return () => window.clearTimeout(timer);
  }, [selectedIndex, scale, previewHtml]);

  useImperativeHandle(
    ref,
    () => ({
      exportPptx: () =>
        new Promise<void>((resolve, reject) => {
          const win = iframeRef.current?.contentWindow;
          if (!win) {
            reject(new Error('Preview is not ready for PPTX export.'));
            return;
          }
          const waiter = {
            resolve,
            reject,
            timer: window.setTimeout(() => {
              const idx = exportWaiters.current.indexOf(waiter);
              if (idx >= 0) {
                exportWaiters.current.splice(idx, 1);
                reject(new Error('PPTX export timed out'));
              }
            }, 15000),
          };
          exportWaiters.current.push(waiter);
          const msg: SlidesPreviewFromParentMessage = {
            source: SLIDES_PREVIEW_MESSAGE_SOURCE,
            type: 'export-pptx',
          };
          win.postMessage(msg, '*');
        }),
      exportPdf: () =>
        new Promise<void>((resolve, reject) => {
          const win = iframeRef.current?.contentWindow;
          if (!win) {
            reject(new Error('Preview is not ready for PDF export.'));
            return;
          }
          const waiter = {
            resolve,
            reject,
            timer: window.setTimeout(() => {
              const idx = exportWaiters.current.indexOf(waiter);
              if (idx >= 0) {
                exportWaiters.current.splice(idx, 1);
                reject(new Error('PDF export timed out'));
              }
            }, SLIDES_PDF_EXPORT_ACK_MS),
          };
          exportWaiters.current.push(waiter);
          const msg: SlidesPreviewFromParentMessage = {
            source: SLIDES_PREVIEW_MESSAGE_SOURCE,
            type: 'export-pdf',
          };
          win.postMessage(msg, '*');
        }),
    }),
    [],
  );

  const scaledW = SLIDES_STAGE_WIDTH * scale;
  const scaledH = docHeight * scale;
  const fitsInHost = hostHeight > 0 && scaledH <= hostHeight + 0.5;
  const topPad = fitsInHost ? Math.max(0, (hostHeight - scaledH) / 2) : 0;

  return (
    <div
      ref={hostRef}
      className={cn('absolute inset-0 overflow-auto bg-muted', className)}
      onScroll={() => {
        if (!onSelectedIndexChange || ignoreScrollRef.current) return;
        const host = hostRef.current;
        if (!host) return;
        const next = slidesPreviewIndexFromScroll(host.scrollTop, scale);
        if (next !== selectedIndex) onSelectedIndexChange(next);
      }}
    >
      <div
        className="relative mx-auto overflow-hidden"
        style={{
          width: scaledW,
          height: scaledH,
          marginTop: topPad,
        }}
      >
        {previewHtml ? (
          <iframe
            ref={iframeRef}
            title={title}
            sandbox="allow-scripts allow-downloads allow-modals"
            srcDoc={previewHtml}
            className={cn(
              'block border-0 transition-opacity duration-150',
              imagesReady ? 'opacity-100' : 'opacity-0',
            )}
            style={{
              width: SLIDES_STAGE_WIDTH,
              height: docHeight,
              transform: `scale(${scale})`,
              transformOrigin: 'top left',
            }}
          />
        ) : null}
        {!imagesReady && (
          <div
            className="absolute inset-0 flex items-center justify-center gap-2 bg-muted text-sm text-muted-foreground"
            aria-hidden="true"
          >
            <Loader2 size={16} className="animate-spin" />
            Loading slides…
          </div>
        )}
      </div>
    </div>
  );
});
