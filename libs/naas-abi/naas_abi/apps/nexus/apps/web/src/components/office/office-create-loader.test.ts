import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { OfficeCreateLoader } from './office-create-loader';

describe('OfficeCreateLoader', () => {
  it('shows a letter page while a document workspace starts', () => {
    const html = renderToStaticMarkup(
      createElement(OfficeCreateLoader, { kind: 'document', phase: 'creating' }),
    );
    expect(html).toContain('data-testid="office-create-loader"');
    expect(html).toContain('data-kind="document"');
    expect(html).toContain('data-phase="creating"');
    expect(html).toContain('Creating workspace…');
    expect(html).toContain('aspect-[8.5/11]');
    expect(html).not.toContain('Opening document…');
  });

  it('switches to opening copy without inventing a second surface', () => {
    const html = renderToStaticMarkup(
      createElement(OfficeCreateLoader, { kind: 'document', phase: 'opening' }),
    );
    expect(html).toContain('data-phase="opening"');
    expect(html).toContain('Opening document…');
  });

  it('uses a 16:9 sheet for Slides', () => {
    const html = renderToStaticMarkup(
      createElement(OfficeCreateLoader, { kind: 'deck', phase: 'opening' }),
    );
    expect(html).toContain('data-kind="deck"');
    expect(html).toContain('Opening presentation…');
    expect(html).toContain('aspect-video');
    expect(html).not.toContain('aspect-[8.5/11]');
  });

  it('surfaces a create error on the same sheet', () => {
    const html = renderToStaticMarkup(
      createElement(OfficeCreateLoader, {
        kind: 'document',
        phase: 'creating',
        error: 'Could not create the document.',
      }),
    );
    expect(html).toContain('data-phase="error"');
    expect(html).toContain('Could not create the document.');
    expect(html).not.toContain('Creating workspace…');
    expect(html).not.toContain('animate-spin');
  });
});
