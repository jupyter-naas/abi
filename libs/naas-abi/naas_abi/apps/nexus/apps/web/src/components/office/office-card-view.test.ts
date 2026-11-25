/**
 * The chat card has to open the document, workbook or deck inside the app shell.
 *
 * A forced new window (target="_blank" or window.open) loses the workspace
 * layout and the chat panel beside the item, so the card must stay a plain
 * link that Next handles client-side. It is still a real anchor, so
 * middle-click and cmd-click keep working.
 */

import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { OfficeCardView } from './office-card-view';
import { OFFICE_KINDS } from './office-kinds';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

const EXPORTS = { documents: 'export PDF', sheets: 'export XLSX', slides: 'export PPTX' };

describe.each(OFFICE_KINDS)('OfficeCardView ($id)', (kind) => {
  function markup(): string {
    return renderToStaticMarkup(
      createElement(OfficeCardView, {
        kind,
        store: { getState: () => ({ setSelectedSlug: () => {}, setSelectedTitle: () => {} }) },
        card: {
          slug: 'materiaux-de-construction',
          title: 'Matériaux de construction',
          workspaceId: 'ws-1',
        },
        currentWorkspaceId: 'ws-current',
      }),
    );
  }

  it('links into the app for the item workspace', () => {
    expect(markup()).toContain(`href="/workspace/ws-1/${kind.id}/materiaux-de-construction"`);
    expect(markup()).toContain(`data-testid="${kind.card.testId}"`);
  });

  it('does not force a new window', () => {
    const html = markup();
    expect(html).not.toContain('target=');
    expect(html).not.toContain('_blank');
  });

  it('shows the item title', () => {
    expect(markup()).toContain('Matériaux de construction');
  });

  it('mentions the export format in the subtitle', () => {
    expect(markup()).toContain(EXPORTS[kind.id]);
  });
});
