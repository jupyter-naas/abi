import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it, vi } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'pdf-viewer.tsx'), 'utf8');

// Minimal shadow root / document fakes: jsdom cannot start on this Node version.
function fakeShadowHost() {
  const children: { tag: string; attrs: Record<string, string>; textContent: string }[] = [];
  return {
    children,
    shadowRoot: {
      appendChild: (node: (typeof children)[number]) => children.push(node),
      querySelector: (selector: string) =>
        selector === 'style[data-nexus-pdf-viewer]'
          ? children.find((c) => c.tag === 'style' && 'data-nexus-pdf-viewer' in c.attrs) ?? null
          : null,
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('PdfViewer resize handling', () => {
  it('leaves window.ResizeObserver native', async () => {
    class NativeResizeObserver {}
    const win = { ResizeObserver: NativeResizeObserver };
    vi.stubGlobal('window', win);
    await import('./pdf-viewer');
    expect(win.ResizeObserver).toBe(NativeResizeObserver);
    expect(src).not.toMatch(/window\.ResizeObserver\s*=/);
    expect(src).not.toContain('/* silence */');
  });

  it('scopes the scrollbar fix to each viewer shadow root, once per instance', async () => {
    vi.stubGlobal('document', {
      createElement: (tag: string) => {
        const attrs: Record<string, string> = {};
        return { tag, attrs, textContent: '', setAttribute: (k: string, v: string) => (attrs[k] = v) };
      },
    });
    const { stabilizePdfViewerScrollbars, PDF_VIEWER_SHADOW_CSS } = await import('./pdf-viewer');
    const a = fakeShadowHost();
    const b = fakeShadowHost();

    stabilizePdfViewerScrollbars(a as unknown as Element);
    stabilizePdfViewerScrollbars(a as unknown as Element);
    stabilizePdfViewerScrollbars(b as unknown as Element);
    stabilizePdfViewerScrollbars(null);
    stabilizePdfViewerScrollbars({ shadowRoot: null } as unknown as Element);

    expect(a.children).toHaveLength(1);
    expect(b.children).toHaveLength(1);
    expect(a.children[0].textContent).toBe(PDF_VIEWER_SHADOW_CSS);
  });

  it('keeps the unmount cleanup that removes the viewer and its observers', () => {
    expect(src).toContain('cancelled = true;');
    expect(src).toContain('host.replaceChildren();');
  });
});
