import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { SlidesProject } from '@/stores/slides';
import { SlidesIndexCard, SlidesIndexGallery, SlidesTemplateStrip } from './slides-index-gallery';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

vi.mock('./slides-cover-thumb', () => ({
  SlidesCoverThumb: ({ title }: { title: string }) =>
    createElement(
      'div',
      { 'data-testid': 'slides-cover-thumb', className: 'relative aspect-video' },
      title,
    ),
  SlidesCoverFallback: ({ title }: { title: string }) =>
    createElement('div', { 'data-testid': 'slides-cover-fallback' }, title),
}));

function project(over: Partial<SlidesProject> = {}): SlidesProject {
  return {
    slug: 'deck-one',
    title: 'Board update',
    branch: 'slides/ws-1/deck-one',
    deck_path: 'slides/ws-1/deck-one/deck.html',
    template_id: 'abi/minimal-light-v1',
    ...over,
  };
}

describe('SlidesIndexCard', () => {
  it('is an Apps-style glass card with a 16:9 thumb and the title', () => {
    const html = renderToStaticMarkup(
      createElement(SlidesIndexCard, {
        project: project(),
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
      }),
    );
    expect(html).toContain('glass-card');
    expect(html).toContain('aspect-video');
    expect(html).toContain('Board update');
    expect(html).toContain('href="/workspace/ws-1/slides/deck-one"');
    expect(html).not.toContain('deck.html');
    expect(html).not.toContain('slides/ws-1/deck-one/deck.html');
  });

  it('adds the chat overflow when rename and archive handlers are passed', () => {
    const html = renderToStaticMarkup(
      createElement(SlidesIndexCard, {
        project: project(),
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
        onRename: () => {},
        onArchive: () => {},
      }),
    );
    expect(html).toContain('data-testid="slides-project-menu"');
  });
});

describe('SlidesIndexGallery', () => {
  it('uses the Apps gallery grid', () => {
    const html = renderToStaticMarkup(
      createElement(SlidesIndexGallery, {
        projects: [project(), project({ slug: 'deck-two', title: 'Second' })],
        workspaceId: 'ws-1',
        templates: [],
        onOpen: () => {},
      }),
    );
    expect(html).toContain('sm:grid-cols-2');
    expect(html).toContain('lg:grid-cols-3');
    expect(html).toContain('data-testid="slides-index-gallery"');
    expect(html).toContain('data-slug="deck-one"');
    expect(html).toContain('data-slug="deck-two"');
  });
});

describe('SlidesTemplateStrip', () => {
  it('shows Blank first, then catalog names, without fetching seed HTML', () => {
    const html = renderToStaticMarkup(
      createElement(SlidesTemplateStrip, {
        templates: [
          {
            id: 'forvis-mazars/fm-slides-v1',
            name: 'Forvis Mazars AI',
            description: '',
            preview_bg: '#f4f4f4',
            preview_panel: '#ffffff',
            preview_accent: '#0072ce',
            preview_ink: '#464b4b',
            slides: [{ index: 0, eyebrow: 'Cover', title: 'Forvis Mazars AI' }],
            assets: [],
          },
          {
            id: 'forvis-mazars/financial-services-v2',
            name: 'Financial services',
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
    expect(html).toContain('Forvis Mazars AI');
    expect(html).toContain('Financial services');
    expect(html).toContain('data-template-id="abi/minimal-light-v1"');
    expect(html).toContain('data-testid="slides-template-blank-thumb"');
    expect(html).not.toContain('>abi/');
    expect(html).not.toContain('/api/slides/projects');
    expect(html.indexOf('Blank')).toBeLessThan(html.indexOf('Forvis Mazars AI'));
  });
});
