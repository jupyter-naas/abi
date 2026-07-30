'use client';

import {
  forwardRef,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type Ref,
} from 'react';
import { cn } from '@/lib/utils';
import {
  computeSlidesPreviewScale,
  prepareSlidesPreviewHtml,
  SLIDES_STAGE_HEIGHT,
  SLIDES_STAGE_WIDTH,
} from './slides-preview-fit';

function assignRef<T>(ref: Ref<T> | undefined, value: T | null) {
  if (!ref) return;
  if (typeof ref === 'function') {
    ref(value);
    return;
  }
  (ref as { current: T | null }).current = value;
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
 */
export const SlidesPreviewFrame = forwardRef<HTMLIFrameElement, SlidesPreviewFrameProps>(
  function SlidesPreviewFrame({ html, className, title = 'Slides preview' }, ref) {
    const hostRef = useRef<HTMLDivElement>(null);
    const iframeRef = useRef<HTMLIFrameElement | null>(null);
    const [scale, setScale] = useState(1);
    const [docHeight, setDocHeight] = useState(SLIDES_STAGE_HEIGHT);
    const [hostHeight, setHostHeight] = useState(0);
    const previewHtml = prepareSlidesPreviewHtml(html);

    const measureHost = useCallback(() => {
      const host = hostRef.current;
      if (!host) return;
      const { width, height } = host.getBoundingClientRect();
      setHostHeight(height);
      setScale(computeSlidesPreviewScale(width, height));
    }, []);

    const measureDoc = useCallback(() => {
      const doc = iframeRef.current?.contentDocument;
      if (!doc) return;
      const body = doc.body;
      const el = doc.documentElement;
      const measured = Math.max(
        body?.scrollHeight ?? 0,
        body?.offsetHeight ?? 0,
        el?.scrollHeight ?? 0,
        el?.offsetHeight ?? 0,
        SLIDES_STAGE_HEIGHT,
      );
      // Snap to whole slides when close (gapless stack after prepare CSS).
      const slides = Math.max(1, Math.round(measured / SLIDES_STAGE_HEIGHT));
      setDocHeight(slides * SLIDES_STAGE_HEIGHT);
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
      // Re-measure after srcDoc swaps (debounced preview updates).
      const id = window.setTimeout(() => measureDoc(), 50);
      return () => window.clearTimeout(id);
    }, [previewHtml, measureDoc]);

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
            ref={(node) => {
              iframeRef.current = node;
              assignRef(ref, node);
            }}
            title={title}
            sandbox="allow-scripts allow-same-origin allow-downloads"
            srcDoc={previewHtml}
            onLoad={() => measureDoc()}
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
  },
);
