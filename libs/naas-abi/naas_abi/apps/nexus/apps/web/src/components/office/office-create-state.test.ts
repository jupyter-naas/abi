import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it } from 'vitest';

import {
  beginOfficeCreate,
  clearOfficeCreate,
  isOfficeCreateNewPath,
  isOfficeCreateProjectPath,
  officeCreateKindFromHref,
  pushOfficeCreate,
  useOfficeCreateStore,
} from './office-create-state';

const here = dirname(fileURLToPath(import.meta.url));

function source(rel: string): string {
  return readFileSync(join(here, rel), 'utf8');
}

afterEach(() => {
  clearOfficeCreate();
});

describe('beginOfficeCreate', () => {
  it('sets the flag before any caller can push, and blocks a second click', () => {
    const order: string[] = [];
    const unsub = useOfficeCreateStore.subscribe((state) => {
      if (state.kind) order.push(`flag:${state.kind}`);
    });
    expect(beginOfficeCreate('document')).toBe(true);
    expect(useOfficeCreateStore.getState().kind).toBe('document');
    expect(beginOfficeCreate('document')).toBe(false);
    expect(beginOfficeCreate('deck')).toBe(false);
    unsub();
    expect(order[0]).toBe('flag:document');
  });
});

describe('pushOfficeCreate', () => {
  it('writes the creating flag and returns before any navigation', () => {
    const order: string[] = [];
    const hrefs: string[] = [];
    const unsub = useOfficeCreateStore.subscribe((state) => {
      if (state.kind) order.push('flag');
    });
    expect(
      pushOfficeCreate(
        {
          push: (href) => {
            order.push('push');
            hrefs.push(href);
          },
          replace: (href) => {
            order.push('replace');
            hrefs.push(href);
          },
        },
        'document',
        'ws-1',
        'abi/article-light-v1',
      ),
    ).toBe(true);
    unsub();
    expect(order).toEqual(['flag']);
    expect(hrefs).toEqual([]);
    expect(useOfficeCreateStore.getState().kind).toBe('document');
  });

  it('does not start a second create while one is in flight', () => {
    const hrefs: string[] = [];
    const router = {
      push: (href: string) => hrefs.push(href),
      replace: (href: string) => hrefs.push(href),
    };
    expect(pushOfficeCreate(router, 'deck', 'ws-1')).toBe(true);
    expect(pushOfficeCreate(router, 'deck', 'ws-1')).toBe(false);
    expect(hrefs).toEqual([]);
  });

  it('does not begin when workspace id is missing', () => {
    expect(
      pushOfficeCreate({ push: () => undefined, replace: () => undefined }, 'document', ''),
    ).toBe(false);
    expect(useOfficeCreateStore.getState().kind).toBeNull();
  });

  it('POSTs from the click, not from the /new route', () => {
    const src = source('./office-create-state.ts');
    expect(src).toContain("import('@/lib/create-documents-project')");
    expect(src).toContain("import('@/lib/create-slides-project')");
    expect(src).toContain('startNewDocument');
    expect(src).toContain('startNewPresentation');
    expect(src).not.toMatch(/router\.push\(officeCreateHref/);
  });
});

describe('officeCreateKindFromHref', () => {
  it('recognizes office /new routes', () => {
    expect(officeCreateKindFromHref('/workspace/ws-1/documents/new')).toBe('document');
    expect(officeCreateKindFromHref('/workspace/ws-1/slides/new?template=x')).toBe('deck');
    expect(officeCreateKindFromHref('/workspace/ws-1/documents')).toBeNull();
  });
});

describe('office create overlay hold', () => {
  it('holds on /new and the new project route, not the gallery', () => {
    expect(isOfficeCreateNewPath('/workspace/ws-1/documents/new')).toBe(true);
    expect(isOfficeCreateNewPath('/workspace/ws-1/slides/new')).toBe(true);
    expect(isOfficeCreateNewPath('/workspace/ws-1/documents/untitled-1')).toBe(false);
    expect(isOfficeCreateNewPath('/workspace/ws-1/documents')).toBe(false);
    expect(isOfficeCreateProjectPath('/workspace/ws-1/documents/untitled-1')).toBe(true);
    expect(isOfficeCreateProjectPath('/workspace/ws-1/slides/untitled-1')).toBe(true);
    expect(isOfficeCreateProjectPath('/workspace/ws-1/documents')).toBe(false);
    expect(isOfficeCreateProjectPath('/workspace/ws-1/home')).toBe(false);
  });

  it('keeps the overlay on the project route and clears after HTML loads', () => {
    const overlay = source('./office-create-overlay.tsx');
    expect(overlay).toContain('isOfficeCreateProjectPath(pathname)');
    expect(overlay).toContain('isOfficeCreateNewPath(pathname)');
    const docPage = source('../../app/workspace/[workspaceId]/documents/[slug]/page.tsx');
    expect(docPage).toContain('clearOfficeCreate()');
    expect(docPage).toContain('void ensureDocumentsRuntime');
    expect(docPage).not.toContain('await ensureDocumentsRuntime');
    const slidesPage = source('../../app/workspace/[workspaceId]/slides/[slug]/page.tsx');
    expect(slidesPage).toContain('clearOfficeCreate()');
    expect(slidesPage).toContain('void ensureSlidesRuntime');
    expect(slidesPage).not.toContain('await ensureSlidesRuntime');
  });
});

describe('New document click paths', () => {
  it('paints via pushOfficeCreate on every Documents entry, with no await before it', () => {
    const files = [
      '../../app/workspace/[workspaceId]/documents/page.tsx',
      '../../app/workspace/[workspaceId]/documents/[slug]/page.tsx',
      '../shell/sidebar/documents-section.tsx',
    ];
    for (const file of files) {
      const src = source(file);
      expect(src).toContain("pushOfficeCreate(router, 'document'");
      expect(src).not.toMatch(/await[\s\S]{0,120}pushOfficeCreate/);
    }
  });

  it('paints via pushOfficeCreate on every Slides entry, with no await before it', () => {
    const files = [
      '../../app/workspace/[workspaceId]/slides/page.tsx',
      '../../app/workspace/[workspaceId]/slides/[slug]/page.tsx',
      '../shell/sidebar/slides-section.tsx',
    ];
    for (const file of files) {
      const src = source(file);
      expect(src).toContain("pushOfficeCreate(router, 'deck'");
      expect(src).not.toMatch(/await[\s\S]{0,120}pushOfficeCreate/);
    }
  });

  it('keeps /documents/new a cheap shell that loads create after first paint', () => {
    const src = source('../../app/workspace/[workspaceId]/documents/new/page.tsx');
    expect(src).not.toMatch(/import\s*\{[^}]*startNewDocument/);
    expect(src).toContain("import('@/lib/create-documents-project')");
    expect(src).toContain('OfficeCreateLoader');
    expect(src).not.toContain('useSearchParams');
  });

  it('keeps /slides/new a cheap shell that loads create after first paint', () => {
    const src = source('../../app/workspace/[workspaceId]/slides/new/page.tsx');
    expect(src).not.toMatch(/import\s*\{[^}]*startNewPresentation/);
    expect(src).toContain("import('@/lib/create-slides-project')");
    expect(src).toContain('OfficeCreateLoader');
    expect(src).not.toContain('useSearchParams');
  });

  it('covers the main canvas from the already-mounted workspace shell', () => {
    const src = source('../shell/workspace-layout.tsx');
    expect(src).toContain('OfficeCreateOverlay');
  });

  it('paints from the command palette and POSTs without waiting for /new', () => {
    const src = source('../shell/quick-open.tsx');
    expect(src).toContain('pushOfficeCreate(router, createKind, currentWorkspaceId)');
    expect(src).toContain('officeCreateKindFromHref(action.href)');
    expect(src).not.toContain('beginOfficeCreate(createKind)');
  });
});

describe('office pane agent bind', () => {
  it('rebinds Slides from the route so a leftover Documents face cannot stay', () => {
    const chat = source('../chat/chat-interface.tsx');
    expect(chat).toContain('officeSurfaceFromPath');
    expect(chat).toContain('pickPaneOfficeAgent');
    expect(chat).not.toMatch(/if \(!isPane \|\| !documentsChatContext\) return/);
    const index = source('../../app/workspace/[workspaceId]/slides/page.tsx');
    expect(index).toContain('pickPaneOfficeAgent');
    expect(index).toContain('onSlides: true');
  });
});
