/**
 * The Slides sidebar tree is a file explorer, so this pins the parts a
 * redesign keeps breaking:
 *
 *   - no section banners, only folders and files;
 *   - decks are anchors into the app, so cmd-click and middle-click work and
 *     a plain click keeps the workspace shell and the chat pane;
 *   - the deck being edited is shown by selection, not by a header;
 *   - decks carry the name Abi generated from the topic.
 */

import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

import { SlidesTreeView } from './slides-tree-view';
import { buildSlidesTree, type SlidesProjectTree } from './slides-tree';
import type { SlidesProject } from '@/stores/slides';

function project(slug: string, title: string): SlidesProject {
  return {
    slug,
    title,
    branch: 'main',
    deck_path: `slides/ws/${slug}/deck.html`,
    template_id: 'minimal-light-v1',
  };
}

const deckTree: SlidesProjectTree = {
  slug: 'materiaux',
  root: 'slides/ws/materiaux',
  entries: [
    { name: 'deck.html', path: 'slides/ws/materiaux/deck.html', type: 'file' },
    { name: 'project.json', path: 'slides/ws/materiaux/project.json', type: 'file' },
    { name: 'assets', path: 'slides/ws/materiaux/assets', type: 'dir' },
  ],
  assets: [{ name: 'logo.png', path: 'slides/ws/materiaux/assets/logo.png', type: 'file' }],
};

const decks = buildSlidesTree(
  [project('materiaux', 'Matériaux de construction'), project('ai-news', 'Latest Ai News 2')],
  { workspaceId: 'ws-1', openSlug: 'materiaux', trees: { materiaux: deckTree } },
);

function markup(props: Record<string, unknown> = {}): string {
  return renderToStaticMarkup(
    createElement(SlidesTreeView, {
      decks,
      rootHref: '/workspace/ws-1/slides',
      currentPath: '/workspace/ws-1/slides/materiaux',
      rootExpanded: true,
      onToggleRoot: () => {},
      expandedDecks: ['materiaux'],
      onToggleDeck: () => {},
      expandedDirs: [],
      onToggleDir: () => {},
      onOpenDeck: () => {},
      ...props,
    } as never),
  );
}

describe('SlidesTreeView', () => {
  it('has no editorial section headers', () => {
    const html = markup();
    for (const banner of ['OPEN PRESENTATION', 'Open presentation', 'TEMPLATES', 'Templates', 'All projects']) {
      expect(html).not.toContain(banner);
    }
  });

  it('shows one root folder holding the decks', () => {
    const html = markup();
    expect(html).toContain('>slides</span>');
    expect((html.match(/data-testid="slides-tree-root"/g) ?? []).length).toBe(1);
  });

  it('lists decks by the name Abi generated', () => {
    const html = markup();
    expect(html).toContain('Matériaux de construction');
    expect(html).toContain('Latest Ai News 2');
  });

  it('links decks into the app instead of a new window', () => {
    const html = markup();
    expect(html).toContain('href="/workspace/ws-1/slides/materiaux"');
    expect(html).toContain('href="/workspace/ws-1/slides/ai-news"');
    expect(html).not.toContain('target=');
    expect(html).not.toContain('_blank');
  });

  it('keeps decks as anchors so cmd-click and middle-click still work', () => {
    const html = markup();
    expect(html).toMatch(/<a[^>]*data-testid="slides-tree-deck"/);
  });

  it('marks the open deck as the current page', () => {
    const html = markup();
    expect(html).toMatch(/data-slug="materiaux"[^>]*aria-current="page"|aria-current="page"[^>]*data-slug="materiaux"/);
    expect((html.match(/aria-current="page"/g) ?? []).length).toBe(1);
  });

  it('does not claim a deck is the current page from the slides index', () => {
    const html = markup({ currentPath: '/workspace/ws-1/slides' });
    expect(html).not.toContain('aria-current');
    // The last deck opened still reads as selected, the way an editor keeps
    // showing which file you were in.
    expect(html).toContain('bg-workspace-accent-15');
  });

  it('shows selection on the open deck and not on the others', () => {
    const html = markup();
    const rows = html.match(/<a[^>]*data-testid="slides-tree-deck"[^>]*>/g) ?? [];
    const selected = rows.filter((row) => row.includes('bg-workspace-accent-15'));
    expect(rows.length).toBe(2);
    expect(selected.length).toBe(1);
    expect(selected[0]).toContain('data-slug="materiaux"');
  });

  it('expands the open deck to the files that exist on disk', () => {
    const html = markup();
    expect(html).toContain('deck.html');
    expect(html).toContain('project.json');
    expect(html).toContain('>assets</span>');
  });

  it('leaves a collapsed deck unexpanded', () => {
    const html = markup({ expandedDecks: [] });
    expect(html).not.toContain('project.json');
  });

  it('hides the whole tree when the root is collapsed', () => {
    const html = markup({ rootExpanded: false });
    expect(html).not.toContain('Matériaux de construction');
    expect(html).toContain('>slides</span>');
  });

  it('gives every folder a real disclosure button', () => {
    const html = markup();
    expect(html).toContain('aria-label="Collapse slides"');
    expect(html).toContain('aria-label="Collapse Matériaux de construction"');
    expect(html).toContain('aria-label="Expand Latest Ai News 2"');
    expect(html).toContain('aria-label="Expand assets"');
  });

  it('nests a fetched asset under the assets folder once opened', () => {
    expect(markup()).not.toContain('logo.png');
    expect(markup({ expandedDirs: ['slides/ws/materiaux/assets'] })).toContain('logo.png');
  });

  it('routes deck.html to its deck', () => {
    const html = markup();
    expect(html).toMatch(/<a[^>]*href="\/workspace\/ws-1\/slides\/materiaux"[^>]*data-testid="slides-tree-file"/);
  });

  it('says so when the workspace has no deck yet', () => {
    expect(markup({ decks: [] })).toContain('No presentations yet');
  });
});
