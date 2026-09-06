/**
 * The Slides sidebar is a file explorer, so its model has to answer three
 * questions without any section headers to lean on: what is under the root,
 * what is inside one deck, and which node is the one the user has open.
 */

import { describe, expect, it } from 'vitest';
import type { SlidesProject } from '@/stores/slides';
import {
  SLIDES_TREE_ROOT_LABEL,
  buildSlidesTree,
  initialExpandedSlidesDecks,
  slidesTreeDeckHref,
  slidesTreeDeckLabel,
  slidesTreeFileNodes,
  type SlidesProjectTree,
} from './slides-tree';

function project(over: Partial<SlidesProject> & { slug: string }): SlidesProject {
  return {
    title: '',
    branch: 'main',
    deck_path: `slides/ws/${over.slug}/deck.html`,
    template_id: 'minimal-light-v1',
    ...over,
  };
}

function tree(over: Partial<SlidesProjectTree> = {}): SlidesProjectTree {
  return {
    slug: 'deck-one',
    root: 'slides/ws/deck-one',
    entries: [
      { name: 'deck.html', path: 'slides/ws/deck-one/deck.html', type: 'file' },
      { name: 'project.json', path: 'slides/ws/deck-one/project.json', type: 'file' },
      { name: 'assets', path: 'slides/ws/deck-one/assets', type: 'dir' },
    ],
    assets: [],
    ...over,
  };
}

describe('slides tree root', () => {
  it('names the root after the folder the decks really live in', () => {
    expect(SLIDES_TREE_ROOT_LABEL).toBe('slides');
  });
});

describe('slidesTreeDeckLabel', () => {
  it('uses the name Abi generated from the topic', () => {
    expect(slidesTreeDeckLabel({ slug: 'untitled-mtq5', title: 'Matériaux de construction' })).toBe(
      'Matériaux de construction',
    );
  });

  it('falls back to the slug while the deck is still unnamed', () => {
    expect(slidesTreeDeckLabel({ slug: 'untitled-mtq5', title: '   ' })).toBe('untitled-mtq5');
  });
});

describe('slidesTreeDeckHref', () => {
  it('stays an in-app slides route', () => {
    expect(slidesTreeDeckHref('ws-1', 'deck-one')).toBe('/workspace/ws-1/slides/deck-one');
  });

  it('escapes a slug that would break the path', () => {
    expect(slidesTreeDeckHref('ws-1', 'a b')).toBe('/workspace/ws-1/slides/a%20b');
  });
});

describe('slidesTreeFileNodes', () => {
  it('has nothing to show before the deck tree is fetched', () => {
    expect(slidesTreeFileNodes(null)).toEqual([]);
  });

  it('sorts the scaffold the way a file explorer would', () => {
    expect(slidesTreeFileNodes(tree()).map((node) => node.name)).toEqual([
      'assets',
      'deck.html',
      'project.json',
    ]);
  });

  it('puts a folder above files that sort before it', () => {
    const nodes = slidesTreeFileNodes(
      tree({
        entries: [
          { name: 'deck.html', path: 'slides/ws/deck-one/deck.html', type: 'file' },
          { name: 'media', path: 'slides/ws/deck-one/media', type: 'dir' },
        ],
      }),
    );
    expect(nodes.map((node) => node.name)).toEqual(['media', 'deck.html']);
  });

  it('nests fetched assets inside the assets folder', () => {
    const nodes = slidesTreeFileNodes(
      tree({
        assets: [
          { name: 'logo.png', path: 'slides/ws/deck-one/assets/logo.png', type: 'file' },
          { name: 'cover.jpg', path: 'slides/ws/deck-one/assets/cover.jpg', type: 'file' },
        ],
      }),
    );
    const assets = nodes.find((node) => node.name === 'assets');
    expect(assets?.children.map((child) => child.name)).toEqual(['cover.jpg', 'logo.png']);
  });

  it('leaves scaffolding out of the tree', () => {
    const nodes = slidesTreeFileNodes(
      tree({
        entries: [
          { name: 'deck.html', path: 'slides/ws/deck-one/deck.html', type: 'file' },
          { name: 'README.md', path: 'slides/ws/deck-one/README.md', type: 'file' },
        ],
        assets: [{ name: '.gitkeep', path: 'slides/ws/deck-one/assets/.gitkeep', type: 'file' }],
      }),
    );
    expect(nodes.map((node) => node.name)).toEqual(['deck.html']);
  });

  it('marks deck.html as the open file only for the deck being edited', () => {
    const openNodes = slidesTreeFileNodes(tree(), { deckOpen: true });
    expect(openNodes.find((node) => node.name === 'deck.html')?.open).toBe(true);
    expect(openNodes.find((node) => node.name === 'project.json')?.open).toBe(false);

    const idleNodes = slidesTreeFileNodes(tree(), { deckOpen: false });
    expect(idleNodes.find((node) => node.name === 'deck.html')?.open).toBe(false);
  });
});

describe('buildSlidesTree', () => {
  const projects = [
    project({ slug: 'zebra-deck', title: 'Zebra deck' }),
    project({ slug: 'materiaux', title: 'Matériaux de construction' }),
  ];

  it('lists every deck once, including the open one', () => {
    const nodes = buildSlidesTree(projects, { workspaceId: 'ws-1', openSlug: 'materiaux' });
    expect(nodes.map((node) => node.slug)).toEqual(['materiaux', 'zebra-deck']);
  });

  it('marks the routed deck active and nothing else', () => {
    const nodes = buildSlidesTree(projects, { workspaceId: 'ws-1', openSlug: 'materiaux' });
    expect(nodes.filter((node) => node.active).map((node) => node.slug)).toEqual(['materiaux']);
  });

  it('marks no deck active when the route has no deck', () => {
    const nodes = buildSlidesTree(projects, { workspaceId: 'ws-1', openSlug: null });
    expect(nodes.some((node) => node.active)).toBe(false);
  });

  it('reports whether a deck has had its files fetched', () => {
    const nodes = buildSlidesTree(projects, {
      workspaceId: 'ws-1',
      openSlug: 'materiaux',
      trees: { materiaux: tree({ slug: 'materiaux' }) },
    });
    const open = nodes.find((node) => node.slug === 'materiaux');
    const other = nodes.find((node) => node.slug === 'zebra-deck');
    expect(open?.filesLoaded).toBe(true);
    expect(open?.files.map((node) => node.name)).toEqual(['assets', 'deck.html', 'project.json']);
    expect(other?.filesLoaded).toBe(false);
    expect(other?.files).toEqual([]);
  });

  it('skips a malformed project rather than rendering a blank row', () => {
    const nodes = buildSlidesTree([project({ slug: '' }), project({ slug: 'ok', title: 'Ok' })], {
      workspaceId: 'ws-1',
    });
    expect(nodes.map((node) => node.slug)).toEqual(['ok']);
  });
});

describe('initialExpandedSlidesDecks', () => {
  it('opens the deck being edited', () => {
    expect(initialExpandedSlidesDecks('materiaux')).toEqual(['materiaux']);
  });

  it('leaves the tree folded when no deck is open', () => {
    expect(initialExpandedSlidesDecks(null)).toEqual([]);
  });
});
