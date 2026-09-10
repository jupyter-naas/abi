/**
 * The document card has to open the document inside the app shell.
 *
 * A forced new window (target="_blank" or window.open) loses the workspace
 * layout and the chat panel beside the document, so the card must stay a plain
 * link that Next handles client-side. It is still a real anchor, so
 * middle-click and cmd-click keep working.
 */

import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DocumentsCardView } from './documents-card-view';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

function markup(): string {
  return renderToStaticMarkup(
    createElement(DocumentsCardView, {
      card: {
        slug: 'materiaux-de-construction',
        title: 'Matériaux de construction',
        workspaceId: 'ws-1',
      },
      currentWorkspaceId: 'ws-current',
    }),
  );
}

describe('DocumentsCardView', () => {
  it('links into the app for the document workspace', () => {
    expect(markup()).toContain('href="/workspace/ws-1/documents/materiaux-de-construction"');
  });

  it('does not force a new window', () => {
    const html = markup();
    expect(html).not.toContain('target=');
    expect(html).not.toContain('_blank');
  });

  it('shows the document title', () => {
    expect(markup()).toContain('Matériaux de construction');
  });
});
