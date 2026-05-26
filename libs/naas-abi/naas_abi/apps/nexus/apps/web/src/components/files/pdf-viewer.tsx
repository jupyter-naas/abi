'use client';

import { useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';

type SnippetModule = typeof import('@embedpdf/snippet');

interface PdfViewerProps {
  src: string;
  className?: string;
}

// Patch ResizeObserver at module load time so all callbacks are deferred through
// requestAnimationFrame. This breaks the synchronous loop that triggers
// "ResizeObserver loop completed with undelivered notifications" — the browser
// only fires that error when callbacks fire synchronously in the same frame.
// Doing this once at module level rather than inside a component avoids the
// race between React's useEffect timing and Next.js dev overlay handlers.
if (typeof window !== 'undefined' && window.ResizeObserver) {
  const Native = window.ResizeObserver;
  // Only patch once even if this module is HMR-reloaded.
  if (!(Native as unknown as { __patchedForPdfViewer?: boolean }).__patchedForPdfViewer) {
    class PatchedResizeObserver extends Native {
      constructor(callback: ResizeObserverCallback) {
        super((entries, observer) => {
          requestAnimationFrame(() => {
            try { callback(entries, observer); } catch { /* silence */ }
          });
        });
      }
    }
    (PatchedResizeObserver as unknown as { __patchedForPdfViewer: boolean }).__patchedForPdfViewer = true;
    window.ResizeObserver = PatchedResizeObserver;
  }
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
