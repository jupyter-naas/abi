import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { SheetsProject } from '@/stores/sheets';
import { SheetsIndexCard, SheetsIndexGallery, SheetsTemplateStrip } from './sheets-index-gallery';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

vi.mock('./sheets-cover-thumb', () => ({
  SheetsCoverThumb: ({ title }: { title: string }) =>
    createElement(
      'div',
      { 'data-testid': 'sheets-cover-thumb', className: 'relative aspect-video' },
      title,
    ),
  SheetsCoverFallback: ({ title }: { title: string }) =>
    createElement('div', { 'data-testid': 'sheets-cover-fallback' }, title),
}));

function project(over: Partial<SheetsProject> = {}): SheetsProject {
  return {
    slug: 'workbook-one',
    title: 'Board update',
    branch: 'sheets/ws-1/workbook-one',
    workbook_path: 'sheets/ws-1/workbook-one/workbook.html',
    template_id: 'abi/grid-light-v1',
    ...over,
  };
}

describe('SheetsIndexCard', () => {
  it('is an Apps-style glass card with a 16:9 thumb and the title', () => {
    const html = renderToStaticMarkup(
      createElement(SheetsIndexCard, {
        project: project(),
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
      }),
    );
    expect(html).toContain('glass-card');
    expect(html).toContain('aspect-video');
    expect(html).toContain('Board update');
    expect(html).toContain('href="/workspace/ws-1/sheets/workbook-one"');
    expect(html).not.toContain('workbook.html');
    expect(html).not.toContain('sheets/ws-1/workbook-one/workbook.html');
  });

  it('adds the chat overflow when rename and archive handlers are passed', () => {
    const html = renderToStaticMarkup(
      createElement(SheetsIndexCard, {
        project: project(),
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
        onRename: () => {},
        onArchive: () => {},
      }),
    );
    expect(html).toContain('data-testid="sheets-project-menu"');
  });
});

describe('SheetsIndexGallery', () => {
  it('uses the Apps gallery grid', () => {
    const html = renderToStaticMarkup(
      createElement(SheetsIndexGallery, {
        projects: [project(), project({ slug: 'workbook-two', title: 'Second' })],
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
      }),
    );
    expect(html).toContain('sm:grid-cols-2');
    expect(html).toContain('lg:grid-cols-3');
    expect(html).toContain('data-testid="sheets-index-gallery"');
    expect(html).toContain('data-slug="workbook-one"');
    expect(html).toContain('data-slug="workbook-two"');
  });
});

describe('SheetsTemplateStrip', () => {
  it('shows Blank first, then catalog names, without fetching seed HTML', () => {
    const html = renderToStaticMarkup(
      createElement(SheetsTemplateStrip, {
        templates: [
          {
            id: 'acme/house-style-v1',
            name: 'House style',
            description: '',
            preview_bg: '#f4f4f4',
            preview_panel: '#ffffff',
            preview_accent: '#0072ce',
            preview_ink: '#464b4b',
            sheets: [{ index: 0, eyebrow: 'Cover', title: 'House style' }],
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
            sheets: [],
            assets: [],
          },
        ],
        onSelect: () => {},
      }),
    );
    expect(html).toContain('data-testid="sheets-template-strip"');
    expect(html).toContain('Start a new workbook');
    expect(html).toContain('Blank');
    expect(html).toContain('House style');
    expect(html).toContain('Industry');
    expect(html).toContain('data-template-id="abi/grid-light-v1"');
    expect(html).toContain('data-testid="sheets-template-blank-thumb"');
    expect(html).not.toContain('>abi/');
    expect(html).not.toContain('/api/sheets/projects');
    expect(html.indexOf('Blank')).toBeLessThan(html.indexOf('House style'));
  });
});
