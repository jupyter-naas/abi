import { describe, expect, it } from 'vitest';
import type { SheetsProject } from '@/stores/sheets';
import {
  SHEETS_ALL_ROW_LABEL,
  SHEETS_TREE_ROOT_LABEL,
  SHEETS_WORKBOOK_FILE_NAME,
  buildSheetsTree,
  initialExpandedSheetsWorkbooks,
  isSheetsGalleryPath,
  isSheetsNestedPath,
  sheetsTreeFileNodes,
  sheetsTreeWorkbookHref,
  sheetsTreeWorkbookLabel,
  type SheetsProjectTree,
} from './sheets-tree';

function project(over: Partial<SheetsProject> & { slug: string }): SheetsProject {
  return {
    title: '',
    branch: 'main',
    workbook_path: `sheets/ws/${over.slug}/workbook.html`,
    template_id: 'abi/grid-light-v1',
    ...over,
  };
}

function tree(over: Partial<SheetsProjectTree> = {}): SheetsProjectTree {
  return {
    slug: 'workbook-one',
    root: 'sheets/ws/workbook-one',
    entries: [
      { name: 'workbook.html', path: 'sheets/ws/workbook-one/workbook.html', type: 'file' },
      { name: 'project.json', path: 'sheets/ws/workbook-one/project.json', type: 'file' },
      { name: 'assets', path: 'sheets/ws/workbook-one/assets', type: 'dir' },
    ],
    assets: [{ name: 'logo.png', path: 'sheets/ws/workbook-one/assets/logo.png', type: 'file' }],
    ...over,
  };
}

describe('sheets tree root', () => {
  it('names the root after the folder the workbooks really live in', () => {
    expect(SHEETS_TREE_ROOT_LABEL).toBe('sheets');
  });

  it('names the gallery row the same way Apps names All apps', () => {
    expect(SHEETS_ALL_ROW_LABEL).toBe('All sheets');
  });
});

describe('sheets gallery path', () => {
  const gallery = '/workspace/ws-1/sheets';

  it('treats the exact sheets route as the gallery', () => {
    expect(isSheetsGalleryPath(gallery, gallery)).toBe(true);
    expect(isSheetsGalleryPath(`${gallery}/`, gallery)).toBe(true);
    expect(isSheetsNestedPath(gallery, gallery)).toBe(false);
  });

  it('treats a workbook slug as nested, not the gallery', () => {
    expect(isSheetsGalleryPath(`${gallery}/runway`, gallery)).toBe(false);
    expect(isSheetsNestedPath(`${gallery}/runway`, gallery)).toBe(true);
  });
});

describe('sheetsTreeWorkbookLabel', () => {
  it('uses the title when present', () => {
    expect(sheetsTreeWorkbookLabel({ slug: 'untitled-a', title: 'Runway' })).toBe('Runway');
  });

  it('falls back to the slug while the workbook is still unnamed', () => {
    expect(sheetsTreeWorkbookLabel({ slug: 'untitled-a', title: '   ' })).toBe('untitled-a');
  });
});

describe('sheetsTreeWorkbookHref', () => {
  it('routes into the sheets editor', () => {
    expect(sheetsTreeWorkbookHref('ws-1', 'runway')).toBe('/workspace/ws-1/sheets/runway');
  });
});

describe('sheetsTreeFileNodes', () => {
  it('marks workbook.html open when the workbook is open', () => {
    const nodes = sheetsTreeFileNodes(tree(), { workbookOpen: true });
    const workbook = nodes.find((n) => n.name === SHEETS_WORKBOOK_FILE_NAME);
    expect(workbook?.open).toBe(true);
  });

  it('nests assets under the assets folder', () => {
    const nodes = sheetsTreeFileNodes(tree());
    const assets = nodes.find((n) => n.name === 'assets');
    expect(assets?.children.map((c) => c.name)).toEqual(['logo.png']);
  });
});

describe('buildSheetsTree', () => {
  it('sorts by label and marks the open workbook active', () => {
    const nodes = buildSheetsTree(
      [project({ slug: 'b', title: 'Beta' }), project({ slug: 'a', title: 'Alpha' })],
      { workspaceId: 'ws-1', openSlug: 'a' },
    );
    expect(nodes.map((n) => n.slug)).toEqual(['a', 'b']);
    expect(nodes[0]?.active).toBe(true);
    expect(nodes[0]?.href).toBe('/workspace/ws-1/sheets/a');
  });

  it('keeps an open workbook that the list omitted', () => {
    const nodes = buildSheetsTree([], {
      workspaceId: 'ws-1',
      openSlug: 'ghost',
      openTitle: 'Ghost',
    });
    expect(nodes).toHaveLength(1);
    expect(nodes[0]?.label).toBe('Ghost');
  });
});

describe('initialExpandedSheetsWorkbooks', () => {
  it('expands only the open workbook', () => {
    expect(initialExpandedSheetsWorkbooks('runway')).toEqual(['runway']);
    expect(initialExpandedSheetsWorkbooks(null)).toEqual([]);
  });
});
