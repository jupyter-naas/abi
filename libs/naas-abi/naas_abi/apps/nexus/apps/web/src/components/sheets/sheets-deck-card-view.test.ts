/**
 * The workbook card has to open the workbook inside the app shell.
 *
 * A forced new window (target="_blank" or window.open) loses the workspace
 * layout and the chat panel beside the workbook, so the card must stay a plain
 * link that Next handles client-side. It is still a real anchor, so
 * middle-click and cmd-click keep working.
 */

import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { SheetsWorkbookCardView } from './sheets-deck-card-view';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

function markup(): string {
  return renderToStaticMarkup(
    createElement(SheetsWorkbookCardView, {
      card: {
        slug: 'materiaux-de-construction',
        title: 'Matériaux de construction',
        workspaceId: 'ws-1',
      },
      currentWorkspaceId: 'ws-current',
    }),
  );
}

describe('SheetsWorkbookCardView', () => {
  it('links into the app for the workbook workspace', () => {
    expect(markup()).toContain('href="/workspace/ws-1/sheets/materiaux-de-construction"');
  });

  it('does not force a new window', () => {
    const html = markup();
    expect(html).not.toContain('target=');
    expect(html).not.toContain('_blank');
  });

  it('shows the workbook title', () => {
    expect(markup()).toContain('Matériaux de construction');
  });

  it('mentions XLSX export in the subtitle', () => {
    expect(markup()).toContain('export XLSX');
  });
});
