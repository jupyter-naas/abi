import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  placeSheetsProjectMenu,
  SheetsProjectOverflowMenu,
  SHEETS_PROJECT_MENU_FOOTER_PX,
  SHEETS_PROJECT_MENU_HEIGHT_PX,
} from './sheets-project-menu';

describe('SheetsProjectOverflowMenu', () => {
  it('uses the chat strings Rename and Archive', () => {
    const html = renderToStaticMarkup(
      createElement(SheetsProjectOverflowMenu, {
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
      createElement(SheetsProjectOverflowMenu, {
        open: false,
        onOpenChange: vi.fn(),
        onRename: vi.fn(),
        onArchive: vi.fn(),
      }),
    );
    expect(html).toContain('data-testid="sheets-project-menu"');
    expect(html).not.toContain('Rename');
  });
});

describe('placeSheetsProjectMenu', () => {
  it('opens below when the pane has room under the kebab', () => {
    const placed = placeSheetsProjectMenu(
      { top: 120, right: 400, bottom: 136 },
      { width: 1280, height: 800 },
    );
    expect(placed.placement).toBe('below');
    expect(placed.top).toBeGreaterThan(136);
    expect(placed.left).toBe(400 - 160);
  });

  it('flips above when the kebab sits on the last row above the footer', () => {
    const viewport = { width: 1280, height: 800 };
    const bottom = viewport.height - SHEETS_PROJECT_MENU_FOOTER_PX - 8;
    const placed = placeSheetsProjectMenu(
      { top: bottom - 16, right: 900, bottom },
      viewport,
    );
    expect(placed.placement).toBe('above');
    expect(placed.top + SHEETS_PROJECT_MENU_HEIGHT_PX).toBeLessThanOrEqual(
      viewport.height - SHEETS_PROJECT_MENU_FOOTER_PX,
    );
    expect(placed.top).toBeLessThan(bottom);
  });
});
