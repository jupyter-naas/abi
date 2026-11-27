/**
 * The Documents, Sheets and Slides sidebars are file explorers, so their model has
 * to answer three questions without any section headers to lean on: what is under
 * the root, what is inside one item, and which node is the one the user has open.
 */

import { describe, expect, it } from 'vitest';
import { OFFICE_KINDS, officeItemHref } from '@/components/office/office-kinds';
import {
  buildOfficeTree,
  initialExpandedItems,
  isOfficeGalleryPath,
  isOfficeNestedPath,
  officeTreeFileNodes,
  officeTreeItemLabel,
  type OfficeProjectTree,
} from './office-tree';

const ROOTS: Record<string, [string, string]> = { documents: ['documents', 'All documents'], sheets: ['sheets', 'All sheets'], slides: ['slides', 'All slides'] };

describe.each(OFFICE_KINDS)('$id tree', (kind) => {
  const file = kind.fileName;
  const dir = `${kind.id}/ws/item-one`;

  function project(over: { slug: string; title?: string }) {
    return { title: '', ...over };
  }

  function tree(over: Partial<OfficeProjectTree> = {}): OfficeProjectTree {
    return {
      slug: 'item-one',
      root: dir,
      entries: [
        { name: file, path: `${dir}/${file}`, type: 'file' },
        { name: 'project.json', path: `${dir}/project.json`, type: 'file' },
        { name: 'assets', path: `${dir}/assets`, type: 'dir' },
      ],
      assets: [{ name: 'logo.png', path: `${dir}/assets/logo.png`, type: 'file' }],
      ...over,
    };
  }

  const nodes = (t: OfficeProjectTree | null, open?: boolean) => officeTreeFileNodes(t, { fileName: file, open });
  /** Files sort by name, case-insensitively, after the folders. */
  const files = [file, 'project.json'].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));

  describe('root', () => {
    it('names the root after the folder the items really live in', () => {
      expect(kind.treeRootLabel).toBe(ROOTS[kind.id][0]);
    });

    it('names the gallery row the same way Apps names All apps', () => {
      expect(kind.allRowLabel).toBe(ROOTS[kind.id][1]);
    });
  });

  describe('gallery path', () => {
    const gallery = `/workspace/ws-1/${kind.id}`;

    it('treats the exact route as the gallery', () => {
      expect(isOfficeGalleryPath(gallery, gallery)).toBe(true);
      expect(isOfficeGalleryPath(`${gallery}/`, gallery)).toBe(true);
      expect(isOfficeNestedPath(gallery, gallery)).toBe(false);
    });

    it('treats an item slug as nested, not the gallery', () => {
      expect(isOfficeGalleryPath(`${gallery}/north-korea`, gallery)).toBe(false);
      expect(isOfficeNestedPath(`${gallery}/north-korea`, gallery)).toBe(true);
      expect(isOfficeNestedPath(`${gallery}/new`, gallery)).toBe(true);
    });
  });

  describe('label and href', () => {
    it('uses the name Abi generated from the topic', () => {
      expect(officeTreeItemLabel({ slug: 'untitled-mtq5', title: 'Matériaux de construction' })).toBe(
        'Matériaux de construction',
      );
    });

    it('falls back to the slug while the item is still unnamed', () => {
      expect(officeTreeItemLabel({ slug: 'untitled-mtq5', title: '   ' })).toBe('untitled-mtq5');
    });

    it('stays an in-app route', () => {
      expect(officeItemHref(kind, 'ws-1', 'item-one')).toBe(`/workspace/ws-1/${kind.id}/item-one`);
    });

    it('escapes a slug that would break the path', () => {
      expect(officeItemHref(kind, 'ws-1', 'a b')).toBe(`/workspace/ws-1/${kind.id}/a%20b`);
    });
  });

  describe('file nodes', () => {
    it('has nothing to show before the item tree is fetched', () => {
      expect(nodes(null)).toEqual([]);
    });

    it('sorts the scaffold the way a file explorer would', () => {
      expect(nodes(tree()).map((node) => node.name)).toEqual(['assets', ...files]);
    });

    it('puts a folder above files that sort before it', () => {
      const listed = nodes(
        tree({
          entries: [
            { name: file, path: `${dir}/${file}`, type: 'file' },
            { name: 'media', path: `${dir}/media`, type: 'dir' },
          ],
        }),
      );
      expect(listed.map((node) => node.name)).toEqual(['media', file]);
    });

    it('nests fetched assets inside the assets folder', () => {
      const listed = nodes(
        tree({
          assets: [
            { name: 'logo.png', path: `${dir}/assets/logo.png`, type: 'file' },
            { name: 'cover.jpg', path: `${dir}/assets/cover.jpg`, type: 'file' },
          ],
        }),
      );
      const assets = listed.find((node) => node.name === 'assets');
      expect(assets?.children.map((child) => child.name)).toEqual(['cover.jpg', 'logo.png']);
    });

    it('hides the seeded assets folder until it holds something', () => {
      // The server appends `assets` whether or not the item has one, so an empty
      // one is a placeholder rather than a folder the user put there.
      expect(nodes(tree({ assets: [] })).map((node) => node.name)).toEqual(files);
    });

    it('keeps an empty folder the user added', () => {
      const listed = nodes(
        tree({
          entries: [
            { name: file, path: `${dir}/${file}`, type: 'file' },
            { name: 'media', path: `${dir}/media`, type: 'dir' },
          ],
          assets: [],
        }),
      );
      expect(listed.map((node) => node.name)).toEqual(['media', file]);
    });

    it('leaves scaffolding out of the tree', () => {
      const listed = nodes(
        tree({
          entries: [
            { name: file, path: `${dir}/${file}`, type: 'file' },
            { name: 'README.md', path: `${dir}/README.md`, type: 'file' },
          ],
          assets: [{ name: '.gitkeep', path: `${dir}/assets/.gitkeep`, type: 'file' }],
        }),
      );
      expect(listed.map((node) => node.name)).toEqual([file]);
    });

    it(`marks ${file} as the open file only for the item being edited`, () => {
      const open = nodes(tree(), true);
      expect(open.find((node) => node.name === file)?.open).toBe(true);
      expect(open.find((node) => node.name === 'project.json')?.open).toBe(false);
      expect(nodes(tree(), false).find((node) => node.name === file)?.open).toBe(false);
    });
  });

  describe('buildOfficeTree', () => {
    const projects = [
      project({ slug: 'zebra-item', title: 'Zebra item' }),
      project({ slug: 'materiaux', title: 'Matériaux de construction' }),
    ];

    it('lists every item once, sorted by name, including the open one', () => {
      const built = buildOfficeTree(kind, projects, { workspaceId: 'ws-1', openSlug: 'materiaux' });
      expect(built.map((node) => node.slug)).toEqual(['materiaux', 'zebra-item']);
    });

    it('marks the routed item active and nothing else', () => {
      const built = buildOfficeTree(kind, projects, { workspaceId: 'ws-1', openSlug: 'materiaux' });
      expect(built.filter((node) => node.active).map((node) => node.slug)).toEqual(['materiaux']);
    });

    it('marks no item active when the route has no item', () => {
      const built = buildOfficeTree(kind, projects, { workspaceId: 'ws-1', openSlug: null });
      expect(built.some((node) => node.active)).toBe(false);
    });

    it('reports whether an item has had its files fetched', () => {
      const built = buildOfficeTree(kind, projects, {
        workspaceId: 'ws-1',
        openSlug: 'materiaux',
        trees: { materiaux: tree({ slug: 'materiaux' }) },
      });
      const open = built.find((node) => node.slug === 'materiaux');
      const other = built.find((node) => node.slug === 'zebra-item');
      expect(open?.filesLoaded).toBe(true);
      expect(open?.href).toBe(`/workspace/ws-1/${kind.id}/materiaux`);
      expect(open?.files.map((node) => node.name)).toEqual(['assets', ...files]);
      expect(open?.files.find((node) => node.name === file)?.open).toBe(true);
      expect(other?.filesLoaded).toBe(false);
      expect(other?.files).toEqual([]);
    });

    it('skips a malformed project rather than rendering a blank row', () => {
      const built = buildOfficeTree(kind, [project({ slug: '' }), project({ slug: 'ok', title: 'Ok' })], {
        workspaceId: 'ws-1',
      });
      expect(built.map((node) => node.slug)).toEqual(['ok']);
    });

    it('still lists the open item when the project list omitted it', () => {
      const built = buildOfficeTree(kind, [], {
        workspaceId: 'ws-1',
        openSlug: 'untitled-mtrrlh2f',
        openTitle: 'Me présenter Sylvain Fréon',
      });
      expect(built.map((node) => node.slug)).toEqual(['untitled-mtrrlh2f']);
      expect(built[0]?.label).toBe('Me présenter Sylvain Fréon');
      expect(built[0]?.active).toBe(true);
    });

    it('does not duplicate the open item when the list already has it', () => {
      const built = buildOfficeTree(kind, projects, {
        workspaceId: 'ws-1',
        openSlug: 'materiaux',
        openTitle: 'Should not replace',
      });
      expect(built.filter((node) => node.slug === 'materiaux')).toHaveLength(1);
      expect(built.find((node) => node.slug === 'materiaux')?.label).toBe('Matériaux de construction');
    });
  });
});

describe('initialExpandedItems', () => {
  it('opens the item being edited', () => {
    expect(initialExpandedItems('materiaux')).toEqual(['materiaux']);
  });

  it('leaves the tree folded when no item is open', () => {
    expect(initialExpandedItems(null)).toEqual([]);
  });
});
