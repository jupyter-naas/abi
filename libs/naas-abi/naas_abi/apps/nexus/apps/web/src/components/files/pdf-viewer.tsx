'use client';

import { useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';

type SnippetModule = typeof import('@embedpdf/snippet');

interface PdfViewerProps {
  src: string;
  className?: string;
}

// The snippet's scroll viewport (inside its shadow root) observes its own size
// and re-lays the pages out. Without a reserved gutter the vertical scrollbar
// appearing narrows the viewport, which re-triggers that observer in the same
// frame ("ResizeObserver loop completed with undelivered notifications").
// Scoped to this viewer's shadow root; window.ResizeObserver stays native.
export const PDF_VIEWER_SHADOW_CSS = '[style*="overflow: auto"] { scrollbar-gutter: stable; }';

export function stabilizePdfViewerScrollbars(instance: Element | null | undefined): void {
  const root = instance?.shadowRoot;
  if (!root || root.querySelector('style[data-nexus-pdf-viewer]')) return;
  const style = document.createElement('style');
  style.setAttribute('data-nexus-pdf-viewer', '');
  style.textContent = PDF_VIEWER_SHADOW_CSS;
  root.appendChild(style);
}

export function PdfViewer({ src, className }: PdfViewerProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<Element | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !src) return;

    let cancelled = false;
    setLoadError(null);

    (async () => {
      try {
        const mod: SnippetModule = await import('@embedpdf/snippet');
        if (cancelled || !hostRef.current) return;

        host.replaceChildren();

        const instance = mod.default.init({
          type: 'container',
          target: host,
          src,
          theme: { preference: resolvedTheme === 'dark' ? 'dark' : 'light' },
        });
        containerRef.current = instance ?? null;
        stabilizePdfViewerScrollbars(instance);

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
      host.replaceChildren();
      containerRef.current = null;
    };
  }, [src, resolvedTheme]);

  return (
    <div
      className={className}
      style={{ position: 'relative', height: '100%', width: '100%', minHeight: 0 }}
    >
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
