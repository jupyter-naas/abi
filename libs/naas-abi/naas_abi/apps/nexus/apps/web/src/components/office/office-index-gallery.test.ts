import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { OfficeCoverFit } from './office-cover-thumb';
import { DOCUMENTS_KIND, OFFICE_KINDS, SHEETS_KIND, SLIDES_KIND, type OfficeKind } from './office-kinds';
import { OfficeIndexCard, OfficeIndexGallery, OfficeTemplateStrip } from './office-index-gallery';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

vi.mock('./office-cover-thumb', () => ({
  OfficeCoverThumb: ({ kind, title }: { kind: OfficeKind; title: string }) =>
    createElement(
      'div',
      { 'data-testid': `${kind.testIdPrefix}-cover-thumb`, className: `relative ${kind.aspectClass}` },
      title,
    ),
  OfficeCoverFallback: ({ kind, title }: { kind: OfficeKind; title: string }) =>
    createElement('div', { 'data-testid': `${kind.testIdPrefix}-cover-fallback` }, title),
}));

const fit = {} as OfficeCoverFit;

describe.each(OFFICE_KINDS)('$id gallery', (kind) => {
  const file = kind.fileName;
  function project(over: { slug?: string; title?: string } = {}) {
    return { slug: 'item-one', title: 'Board update', template_id: 'abi/minimal-light-v1', ...over };
  }

  describe('OfficeIndexCard', () => {
    it(`is an Apps-style glass card with a ${kind.aspectClass} thumb and the title`, () => {
      const html = renderToStaticMarkup(
        createElement(OfficeIndexCard, { kind, fit, project: project(), workspaceId: 'ws-1', templates: [], onOpen: () => {} }),
      );
      expect(html).toContain('glass-card');
      expect(html).toContain(kind.aspectClass);
      expect(html).toContain('Board update');
      expect(html).toContain(`data-testid="${kind.testIdPrefix}-index-card"`);
      expect(html).toContain(`href="/workspace/ws-1/${kind.id}/item-one"`);
      expect(html).not.toContain(file);
    });

    it('adds the chat overflow when rename and archive handlers are passed', () => {
      const html = renderToStaticMarkup(
        createElement(OfficeIndexCard, {
          kind,
          fit,
          project: project(),
          workspaceId: 'ws-1',
          templates: [],
          onOpen: () => {},
          onRename: () => {},
          onArchive: () => {},
        }),
      );
      expect(html).toContain(`data-testid="${kind.id}-project-menu"`);
    });
  });

  describe('OfficeIndexGallery', () => {
    it('uses the Apps gallery grid', () => {
      const html = renderToStaticMarkup(
        createElement(OfficeIndexGallery, {
          kind,
          fit,
          projects: [project(), project({ slug: 'item-two', title: 'Second' })],
          workspaceId: 'ws-1',
          templates: [],
          onOpen: () => {},
        }),
      );
      expect(html).toContain('sm:grid-cols-2');
      expect(html).toContain('lg:grid-cols-3');
      expect(html).toContain(`data-testid="${kind.id}-index-gallery"`);
      expect(html).toContain('data-slug="item-one"');
      expect(html).toContain('data-slug="item-two"');
    });
  });
});

describe('OfficeTemplateStrip (documents)', () => {
  it('lists catalog names without inventing a Blank card or fetching seed HTML', () => {
    const html = renderToStaticMarkup(
      createElement(OfficeTemplateStrip, {
        kind: DOCUMENTS_KIND,
        templates: [
          {
            id: 'acme/house-style-v1',
            name: 'House style',
            description: '',
            preview_bg: '#f4f4f4',
            preview_panel: '#ffffff',
            preview_accent: '#0072ce',
            preview_ink: '#464b4b',
            sections: [{ index: 0, eyebrow: 'Cover', title: 'House style' }],
            assets: [],
          },
          {
            id: 'acme/industry-v2',
            name: 'Industry',
            description: '',
            preview_bg: '#111111',
            preview_panel: '#ffffff',
            preview_accent: '#0072ce',
            preview_ink: '#464b4b',
            sections: [],
            assets: [],
          },
        ],
        onSelect: () => {},
      }),
    );
    expect(html).toContain('data-testid="sections-template-strip"');
    expect(html).toContain('Start a new document');
    expect(html).toContain('House style');
    expect(html).toContain('Industry');
    expect(html).toContain('data-template-id="acme/house-style-v1"');
    expect(html).not.toContain('Blank');
    expect(html).not.toContain('data-testid="sections-template-blank-thumb"');
    expect(html).not.toContain('>abi/');
    expect(html).not.toContain('/api/documents/projects');
    expect(html.indexOf('House style')).toBeLessThan(html.indexOf('Industry'));
  });
});

describe('OfficeTemplateStrip (sheets)', () => {
  it('shows Blank first, then catalog names, without fetching seed HTML', () => {
    const html = renderToStaticMarkup(
      createElement(OfficeTemplateStrip, {
        kind: SHEETS_KIND,
        templates: [
          {
            id: 'abi/grid-light-v1',
            name: 'Blank',
            description: '',
            preview_bg: '#f3f3f3',
            preview_panel: '#ffffff',
            preview_accent: '#1a73e8',
            preview_ink: '#202124',
            sheets: [{ index: 0, eyebrow: '', title: 'Sheet1' }],
            assets: [],
          },
          {
            id: 'abi/monthly-pnl-v1',
            name: 'Monthly P&L',
            description: '',
            preview_bg: '#eef3f8',
            preview_panel: '#ffffff',
            preview_accent: '#0b57d0',
            preview_ink: '#1f1f1f',
            sheets: [{ index: 0, eyebrow: '', title: 'P&L' }],
            assets: [],
          },
          {
            id: 'abi/budget-vs-actuals-v1',
            name: 'Budget vs Actuals',
            description: '',
            preview_bg: '#f1f5f0',
            preview_panel: '#ffffff',
            preview_accent: '#137333',
            preview_ink: '#1f1f1f',
            sheets: [{ index: 0, eyebrow: '', title: 'Summary' }],
            assets: [],
          },
          {
            id: 'abi/cash-runway-v1',
            name: 'Cash Runway',
            description: '',
            preview_bg: '#f7f2ea',
            preview_panel: '#ffffff',
            preview_accent: '#b06000',
            preview_ink: '#1f1f1f',
            sheets: [{ index: 0, eyebrow: '', title: 'Runway' }],
            assets: [],
          },
        ],
        onSelect: () => {},
      }),
    );
    expect(html).toContain('data-testid="sheets-template-strip"');
    expect(html).toContain('Start a new workbook');
    expect(html).toContain('Blank');
    expect(html).toContain('Monthly P&amp;L');
    expect(html).toContain('Budget vs Actuals');
    expect(html).toContain('Cash Runway');
    expect(html).toContain('data-template-id="abi/grid-light-v1"');
    expect(html).toContain('data-template-id="abi/monthly-pnl-v1"');
    expect(html).toContain('data-testid="sheets-template-blank-thumb"');
    expect(html).not.toContain('>abi/');
    expect(html).not.toContain('/api/sheets/projects');
    expect(html.indexOf('Blank')).toBeLessThan(html.indexOf('Monthly P&amp;L'));
  });
});

describe('OfficeTemplateStrip (slides)', () => {
  it('shows Blank first, then catalog names, without fetching seed HTML', () => {
    const html = renderToStaticMarkup(
      createElement(OfficeTemplateStrip, {
        kind: SLIDES_KIND,
        templates: [
          {
            id: 'acme/house-style-v1',
            name: 'House style',
            description: '',
            preview_bg: '#f4f4f4',
            preview_panel: '#ffffff',
            preview_accent: '#0072ce',
            preview_ink: '#464b4b',
            slides: [{ index: 0, eyebrow: 'Cover', title: 'House style' }],
            assets: [],
          },
          {
            id: 'acme/industry-v2',
            name: 'Industry',
            description: '',
            preview_bg: '#111111',
            preview_panel: '#ffffff',
            preview_accent: '#0072ce',
            preview_ink: '#464b4b',
            slides: [],
            assets: [],
          },
        ],
        onSelect: () => {},
      }),
    );
    expect(html).toContain('data-testid="slides-template-strip"');
    expect(html).toContain('Start a new presentation');
    expect(html).toContain('Blank');
    expect(html).toContain('House style');
    expect(html).toContain('Industry');
    expect(html).toContain('data-template-id="abi/minimal-light-v1"');
    expect(html).toContain('data-testid="slides-template-blank-thumb"');
    expect(html).not.toContain('>abi/');
    expect(html).not.toContain('/api/slides/projects');
    expect(html.indexOf('Blank')).toBeLessThan(html.indexOf('House style'));
  });
});
