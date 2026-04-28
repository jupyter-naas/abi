'use client';

import { useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';

type SnippetModule = typeof import('@embedpdf/snippet');

interface PdfViewerProps {
  src: string;
  className?: string;
}

// Mounts the @embedpdf/snippet web-component viewer (PDFium WASM under the hood)
// inside a host div. We dynamically import the module so the ~MB-class WASM/JS
// payload is only fetched when a PDF is actually opened.
export function PdfViewer({ src, className }: PdfViewerProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<Element | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { resolvedTheme } = useTheme();

  // Suppress the harmless "ResizeObserver loop completed with undelivered
  // notifications" warning that the viewer's internal layout observers can
  // emit. Next.js's dev error overlay otherwise turns it into a toast.
  useEffect(() => {
    const RESIZE_MSG = 'ResizeObserver loop completed with undelivered notifications';
    const onError = (e: ErrorEvent) => {
      if (e.message?.includes(RESIZE_MSG)) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    };
    window.addEventListener('error', onError);
    return () => window.removeEventListener('error', onError);
  }, []);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !src) return;

    let cancelled = false;
    setLoadError(null);

    (async () => {
      try {
        const mod: SnippetModule = await import('@embedpdf/snippet');
        if (cancelled || !hostRef.current) return;

        // Tear down any prior instance before mounting a new one.
        host.replaceChildren();

        const instance = mod.default.init({
          type: 'container',
          target: host,
          src,
          theme: { preference: resolvedTheme === 'dark' ? 'dark' : 'light' },
        });
        containerRef.current = instance ?? null;

        // The snippet mounts an <embedpdf-container> custom element; by default
        // custom elements are display:inline and don't fill their parent,
        // which leaves the inner scroll viewport unbounded. Force it to fill
        // the host so the viewer's own scrolling/zoom can work.
        if (instance instanceof HTMLElement) {
          instance.style.position = 'absolute';
          instance.style.inset = '0';
          instance.style.display = 'block';
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : 'Failed to load PDF viewer');
        }
      }
    })();

    return () => {
      cancelled = true;
      // Removing children triggers the web-component's disconnectedCallback,
      // which disposes the engine and releases the WASM document.
      host.replaceChildren();
      containerRef.current = null;
    };
  }, [src, resolvedTheme]);

  return (
    <div
      className={className}
      style={{ position: 'relative', height: '100%', width: '100%', minHeight: 0 }}
    >
      {/* Absolute fill guarantees a concrete pixel height for the snippet's
          internal scroll viewport, regardless of the surrounding flex chain. */}
      <div
        ref={hostRef}
        style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}
      />
      {loadError && (
        <div className="absolute inset-0 flex items-center justify-center p-6 text-sm text-destructive">
          {loadError}
        </div>
      )}
    </div>
  );
}
