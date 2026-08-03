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
import { cn } from '@/lib/utils';
import {
  computeSlidesPreviewScale,
  isSlidesPreviewMessage,
  prepareSlidesPreviewHtml,
  SLIDES_PREVIEW_MESSAGE_SOURCE,
  SLIDES_STAGE_HEIGHT,
  SLIDES_STAGE_WIDTH,
  type SlidesPreviewFromParentMessage,
} from './slides-preview-fit';

export interface SlidesPreviewFrameHandle {
  exportPptx: () => Promise<void>;
}

export interface SlidesPreviewFrameProps {
  html: string;
  className?: string;
  title?: string;
}

/**
 * Present-style preview: fixed 1280x720 stage scaled with object-fit:contain
 * into the available center pane (letterbox OK). Multi-slide decks scroll at
 * the same scale so no slide content is clipped horizontally.
 *
 * Sandbox omits allow-same-origin so deck scripts cannot touch Nexus storage
 * or make credentialed same-origin requests. Height and PPTX export use a
 * constrained postMessage bridge injected into srcDoc.
 */
export const SlidesPreviewFrame = forwardRef<
  SlidesPreviewFrameHandle,
  SlidesPreviewFrameProps
>(function SlidesPreviewFrame({ html, className, title = 'Slides preview' }, ref) {
  const hostRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [scale, setScale] = useState(1);
  const [docHeight, setDocHeight] = useState(SLIDES_STAGE_HEIGHT);
  const [hostHeight, setHostHeight] = useState(0);
  const previewHtml = prepareSlidesPreviewHtml(html);
  const exportWaiters = useRef<
    Array<{
      resolve: () => void;
      reject: (error: Error) => void;
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
      if (event.data.type === 'metrics' || event.data.type === 'ready') {
        if (typeof event.data.height === 'number' && event.data.height > 0) {
          setDocHeight(event.data.height);
        }
        return;
      }
      if (event.data.type === 'export-pptx-result') {
        const waiters = exportWaiters.current.splice(0);
        if (event.data.ok) {
          waiters.forEach((w) => w.resolve());
        } else {
          const err = new Error(event.data.error || 'PPTX export failed');
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
          exportWaiters.current.push({ resolve, reject });
          const msg: SlidesPreviewFromParentMessage = {
            source: SLIDES_PREVIEW_MESSAGE_SOURCE,
            type: 'export-pptx',
          };
          win.postMessage(msg, '*');
          window.setTimeout(() => {
            const idx = exportWaiters.current.findIndex((w) => w.resolve === resolve);
            if (idx >= 0) {
              exportWaiters.current.splice(idx, 1);
              reject(new Error('PPTX export timed out'));
            }
          }, 15000);
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
      className={cn('absolute inset-0 overflow-auto bg-neutral-950', className)}
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
          sandbox="allow-scripts allow-downloads"
          srcDoc={previewHtml}
          className="block border-0 bg-black"
          style={{
            width: SLIDES_STAGE_WIDTH,
            height: docHeight,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
          }}
        />
      </div>
    </div>
  );
});
