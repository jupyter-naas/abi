import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  placeSlidesProjectMenu,
  SlidesProjectOverflowMenu,
  SLIDES_PROJECT_MENU_FOOTER_PX,
  SLIDES_PROJECT_MENU_HEIGHT_PX,
} from './slides-project-menu';

describe('SlidesProjectOverflowMenu', () => {
  it('uses the chat strings Rename and Archive', () => {
    const html = renderToStaticMarkup(
      createElement(SlidesProjectOverflowMenu, {
        open: true,
        onOpenChange: () => {},
        onRename: () => {},
        onArchive: () => {},
      }),
    );
    expect(html).toContain('Rename');
    expect(html).toContain('Archive');
    expect(html).not.toContain('Delete');
    expect(html).not.toContain('Pin');
  });

  it('hides the menu until the kebab is open', () => {
    const html = renderToStaticMarkup(
      createElement(SlidesProjectOverflowMenu, {
        open: false,
        onOpenChange: vi.fn(),
        onRename: vi.fn(),
        onArchive: vi.fn(),
      }),
    );
    expect(html).toContain('data-testid="slides-project-menu"');
    expect(html).not.toContain('Rename');
  });
});

describe('placeSlidesProjectMenu', () => {
  it('opens below when the pane has room under the kebab', () => {
    const placed = placeSlidesProjectMenu(
      { top: 120, right: 400, bottom: 136 },
      { width: 1280, height: 800 },
    );
    expect(placed.placement).toBe('below');
    expect(placed.top).toBeGreaterThan(136);
    expect(placed.left).toBe(400 - 160);
  });

  it('flips above when the kebab sits on the last row above the footer', () => {
    const viewport = { width: 1280, height: 800 };
    const bottom = viewport.height - SLIDES_PROJECT_MENU_FOOTER_PX - 8;
    const placed = placeSlidesProjectMenu(
      { top: bottom - 16, right: 900, bottom },
      viewport,
    );
    expect(placed.placement).toBe('above');
    expect(placed.top + SLIDES_PROJECT_MENU_HEIGHT_PX).toBeLessThanOrEqual(
      viewport.height - SLIDES_PROJECT_MENU_FOOTER_PX,
    );
    expect(placed.top).toBeLessThan(bottom);
  });
});
