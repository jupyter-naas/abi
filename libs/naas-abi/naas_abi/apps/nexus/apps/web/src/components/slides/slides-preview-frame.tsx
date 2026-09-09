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
}

/**
 * Present-style preview: fixed 1280x720 stage scaled with object-fit:contain
 * into the available center pane (letterbox OK). Multi-slide decks scroll at
 * the same scale so no slide content is clipped horizontally.
 *
 * Sandbox omits allow-same-origin so deck scripts cannot touch Nexus storage
 * or make credentialed same-origin requests. Height, PPTX, and PDF export use
 * a constrained postMessage bridge injected into srcDoc. allow-modals is
 * required so File, Print / Save as PDF can open the browser print dialog.
 *
 * Relative ``assets/`` paths 404 inside srcDoc. The parent fetches the slides
 * asset route with Bearer auth and inlines data-URLs before setting srcDoc.
 *
 * The iframe stays transparent (and a spinner shows) until the in-frame
 * bridge script reports every `<img>` has loaded/errored ('images-ready'),
 * so slides never flash in with blank image boxes. A timeout reveals the
 * preview anyway if that ack never arrives.
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
  },
  ref,
) {
  const hostRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [scale, setScale] = useState(1);
  const [docHeight, setDocHeight] = useState(SLIDES_STAGE_HEIGHT);
  const [hostHeight, setHostHeight] = useState(0);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  // True once every `<img>` in the srcDoc has loaded (or errored) — gates the
  // iframe's visibility so slides don't flash in with blank image boxes
  // while assets are still resolving / painting.
  const [imagesReady, setImagesReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setImagesReady(false);
    void resolveSlidesPreviewAssets(html, workspaceId, slug).then((resolved) => {
      if (!cancelled) setPreviewHtml(prepareSlidesPreviewHtml(resolved));
    });
    return () => {
      cancelled = true;
    };
  }, [html, workspaceId, slug]);

  useEffect(() => {
    if (imagesReady) return;
    const timer = window.setTimeout(() => setImagesReady(true), SLIDES_PREVIEW_IMAGES_READY_TIMEOUT_MS);
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
          setDocHeight(event.data.height);
        }
        if (event.data.type === 'images-ready') setImagesReady(true);
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
  }, []);

  useEffect(() => {
    // Reset height while a new srcDoc loads; bridge will report metrics.
    setDocHeight(SLIDES_STAGE_HEIGHT);
  }, [previewHtml]);

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
          // Timeout only if the iframe never acks that print() was invoked.
          // Success is "print dialog opened", not "user finished Save as PDF".
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
  // Center a short deck in the pane; top-align when content scrolls.
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
        className="mx-auto"
        style={{
          width: scaledW,
          height: scaledH,
          marginTop: topPad,
          position: 'relative',
        }}
      >
        <iframe
          ref={iframeRef}
          title={title}
          sandbox="allow-scripts allow-downloads allow-modals"
          srcDoc={previewHtml ?? ''}
          className={cn(
            'block border-0 bg-white transition-opacity duration-150',
            imagesReady ? 'opacity-100' : 'opacity-0',
          )}
          style={{
            width: SLIDES_STAGE_WIDTH,
            height: docHeight,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
          }}
        />
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
