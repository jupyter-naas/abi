import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { DocumentsProject } from '@/stores/documents';
import { SectionsIndexCard, DocumentsIndexGallery, SectionsTemplateStrip } from './documents-index-gallery';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

vi.mock('./documents-cover-thumb', () => ({
  SectionsCoverThumb: ({ title }: { title: string }) =>
    createElement(
      'div',
      { 'data-testid': 'sections-cover-thumb', className: 'relative aspect-video' },
      title,
    ),
  SectionsCoverFallback: ({ title }: { title: string }) =>
    createElement('div', { 'data-testid': 'sections-cover-fallback' }, title),
}));

function project(over: Partial<DocumentsProject> = {}): DocumentsProject {
  return {
    slug: 'document-one',
    title: 'Board update',
    branch: 'documents/ws-1/document-one',
    document_path: 'documents/ws-1/document-one/document.html',
    template_id: 'abi/minimal-light-v1',
    ...over,
  };
}

describe('SectionsIndexCard', () => {
  it('is an Apps-style glass card with a 16:9 thumb and the title', () => {
    const html = renderToStaticMarkup(
      createElement(SectionsIndexCard, {
        project: project(),
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
      }),
    );
    expect(html).toContain('glass-card');
    expect(html).toContain('aspect-video');
    expect(html).toContain('Board update');
    expect(html).toContain('href="/workspace/ws-1/documents/document-one"');
    expect(html).not.toContain('document.html');
    expect(html).not.toContain('documents/ws-1/document-one/document.html');
  });

  it('adds the chat overflow when rename and archive handlers are passed', () => {
    const html = renderToStaticMarkup(
      createElement(SectionsIndexCard, {
        project: project(),
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
        onRename: () => {},
        onArchive: () => {},
      }),
    );
    expect(html).toContain('data-testid="documents-project-menu"');
  });
});

describe('DocumentsIndexGallery', () => {
  it('uses the Apps gallery grid', () => {
    const html = renderToStaticMarkup(
      createElement(DocumentsIndexGallery, {
        projects: [project(), project({ slug: 'document-two', title: 'Second' })],
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
      }),
    );
    expect(html).toContain('sm:grid-cols-2');
    expect(html).toContain('lg:grid-cols-3');
    expect(html).toContain('data-testid="documents-index-gallery"');
    expect(html).toContain('data-slug="document-one"');
    expect(html).toContain('data-slug="document-two"');
  });
});

describe('SectionsTemplateStrip', () => {
  it('shows Blank first, then catalog names, without fetching seed HTML', () => {
    const html = renderToStaticMarkup(
      createElement(SectionsTemplateStrip, {
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
    expect(html).toContain('Blank');
    expect(html).toContain('House style');
    expect(html).toContain('Industry');
    expect(html).toContain('data-template-id="abi/minimal-light-v1"');
    expect(html).toContain('data-testid="sections-template-blank-thumb"');
    expect(html).not.toContain('>abi/');
    expect(html).not.toContain('/api/documents/projects');
    expect(html.indexOf('Blank')).toBeLessThan(html.indexOf('House style'));
  });
});
