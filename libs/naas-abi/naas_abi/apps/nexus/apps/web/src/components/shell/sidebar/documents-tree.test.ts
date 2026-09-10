/**
 * The Documents sidebar is a file explorer, so its model has to answer three
 * questions without any section headers to lean on: what is under the root,
 * what is inside one document, and which node is the one the user has open.
 */

import { describe, expect, it } from 'vitest';
import type { DocumentsProject } from '@/stores/documents';
import {
  SLIDES_ALL_ROW_LABEL,
  SLIDES_TREE_ROOT_LABEL,
  buildSectionsTree,
  initialExpandedDocuments,
  isSectionsGalleryPath,
  isDocumentsNestedPath,
  sectionsTreeDocumentHref,
  sectionsTreeDocumentLabel,
  sectionsTreeFileNodes,
  type DocumentsProjectTree,
} from './documents-tree';

function project(over: Partial<DocumentsProject> & { slug: string }): DocumentsProject {
  return {
    title: '',
    branch: 'main',
    document_path: `documents/ws/${over.slug}/document.html`,
    template_id: 'minimal-light-v1',
    ...over,
  };
}

function tree(over: Partial<DocumentsProjectTree> = {}): DocumentsProjectTree {
  return {
    slug: 'document-one',
    root: 'documents/ws/document-one',
    entries: [
      { name: 'document.html', path: 'documents/ws/document-one/document.html', type: 'file' },
      { name: 'project.json', path: 'documents/ws/document-one/project.json', type: 'file' },
      { name: 'assets', path: 'documents/ws/document-one/assets', type: 'dir' },
    ],
    assets: [{ name: 'logo.png', path: 'documents/ws/document-one/assets/logo.png', type: 'file' }],
    ...over,
  };
}

describe('sections tree root', () => {
  it('names the root after the folder the documents really live in', () => {
    expect(SLIDES_TREE_ROOT_LABEL).toBe('documents');
  });

  it('names the gallery row the same way Apps names All apps', () => {
    expect(SLIDES_ALL_ROW_LABEL).toBe('All sections');
  });
});

describe('sections gallery path', () => {
  const gallery = '/workspace/ws-1/documents';

  it('treats the exact sections route as the gallery', () => {
    expect(isSectionsGalleryPath(gallery, gallery)).toBe(true);
    expect(isSectionsGalleryPath(`${gallery}/`, gallery)).toBe(true);
    expect(isDocumentsNestedPath(gallery, gallery)).toBe(false);
  });

  it('treats a document slug as nested, not the gallery', () => {
    expect(isSectionsGalleryPath(`${gallery}/north-korea`, gallery)).toBe(false);
    expect(isDocumentsNestedPath(`${gallery}/north-korea`, gallery)).toBe(true);
    expect(isDocumentsNestedPath(`${gallery}/new`, gallery)).toBe(true);
  });
});

describe('sectionsTreeDocumentLabel', () => {
  it('uses the name Abi generated from the topic', () => {
    expect(sectionsTreeDocumentLabel({ slug: 'untitled-mtq5', title: 'Matériaux de construction' })).toBe(
      'Matériaux de construction',
    );
  });

  it('falls back to the slug while the document is still unnamed', () => {
    expect(sectionsTreeDocumentLabel({ slug: 'untitled-mtq5', title: '   ' })).toBe('untitled-mtq5');
  });
});

describe('sectionsTreeDocumentHref', () => {
  it('stays an in-app sections route', () => {
    expect(sectionsTreeDocumentHref('ws-1', 'document-one')).toBe('/workspace/ws-1/documents/document-one');
  });

  it('escapes a slug that would break the path', () => {
    expect(sectionsTreeDocumentHref('ws-1', 'a b')).toBe('/workspace/ws-1/documents/a%20b');
  });
});

describe('sectionsTreeFileNodes', () => {
  it('has nothing to show before the document tree is fetched', () => {
    expect(sectionsTreeFileNodes(null)).toEqual([]);
  });

  it('sorts the scaffold the way a file explorer would', () => {
    expect(sectionsTreeFileNodes(tree()).map((node) => node.name)).toEqual([
      'assets',
      'document.html',
      'project.json',
    ]);
  });

  it('puts a folder above files that sort before it', () => {
    const nodes = sectionsTreeFileNodes(
      tree({
        entries: [
          { name: 'document.html', path: 'documents/ws/document-one/document.html', type: 'file' },
          { name: 'media', path: 'documents/ws/document-one/media', type: 'dir' },
        ],
      }),
    );
    expect(nodes.map((node) => node.name)).toEqual(['media', 'document.html']);
  });

  it('nests fetched assets inside the assets folder', () => {
    const nodes = sectionsTreeFileNodes(
      tree({
        assets: [
          { name: 'logo.png', path: 'documents/ws/document-one/assets/logo.png', type: 'file' },
          { name: 'cover.jpg', path: 'documents/ws/document-one/assets/cover.jpg', type: 'file' },
        ],
      }),
    );
    const assets = nodes.find((node) => node.name === 'assets');
    expect(assets?.children.map((child) => child.name)).toEqual(['cover.jpg', 'logo.png']);
  });

  it('hides the seeded assets folder until it holds something', () => {
    // The server appends `assets` whether or not the document has one, so an empty
    // one is a placeholder rather than a folder the user put there.
    const nodes = sectionsTreeFileNodes(tree({ assets: [] }));
    expect(nodes.map((node) => node.name)).toEqual(['document.html', 'project.json']);
  });

  it('keeps the assets folder once it holds a file', () => {
    const nodes = sectionsTreeFileNodes(
      tree({ assets: [{ name: 'logo.png', path: 'documents/ws/document-one/assets/logo.png', type: 'file' }] }),
    );
    expect(nodes.map((node) => node.name)).toEqual(['assets', 'document.html', 'project.json']);
  });

  it('keeps an empty folder the user added', () => {
    const nodes = sectionsTreeFileNodes(
      tree({
        entries: [
          { name: 'document.html', path: 'documents/ws/document-one/document.html', type: 'file' },
          { name: 'media', path: 'documents/ws/document-one/media', type: 'dir' },
        ],
        assets: [],
      }),
    );
    expect(nodes.map((node) => node.name)).toEqual(['media', 'document.html']);
  });

  it('leaves scaffolding out of the tree', () => {
    const nodes = sectionsTreeFileNodes(
      tree({
        entries: [
          { name: 'document.html', path: 'documents/ws/document-one/document.html', type: 'file' },
          { name: 'README.md', path: 'documents/ws/document-one/README.md', type: 'file' },
        ],
        assets: [{ name: '.gitkeep', path: 'documents/ws/document-one/assets/.gitkeep', type: 'file' }],
      }),
    );
    expect(nodes.map((node) => node.name)).toEqual(['document.html']);
  });

  it('marks document.html as the open file only for the document being edited', () => {
    const openNodes = sectionsTreeFileNodes(tree(), { documentOpen: true });
    expect(openNodes.find((node) => node.name === 'document.html')?.open).toBe(true);
    expect(openNodes.find((node) => node.name === 'project.json')?.open).toBe(false);

    const idleNodes = sectionsTreeFileNodes(tree(), { documentOpen: false });
    expect(idleNodes.find((node) => node.name === 'document.html')?.open).toBe(false);
  });
});

describe('buildSectionsTree', () => {
  const projects = [
    project({ slug: 'zebra-document', title: 'Zebra document' }),
    project({ slug: 'materiaux', title: 'Matériaux de construction' }),
  ];

  it('lists every document once, including the open one', () => {
    const nodes = buildSectionsTree(projects, { workspaceId: 'ws-1', openSlug: 'materiaux' });
    expect(nodes.map((node) => node.slug)).toEqual(['materiaux', 'zebra-document']);
  });

  it('marks the routed document active and nothing else', () => {
    const nodes = buildSectionsTree(projects, { workspaceId: 'ws-1', openSlug: 'materiaux' });
    expect(nodes.filter((node) => node.active).map((node) => node.slug)).toEqual(['materiaux']);
  });

  it('marks no document active when the route has no document', () => {
    const nodes = buildSectionsTree(projects, { workspaceId: 'ws-1', openSlug: null });
    expect(nodes.some((node) => node.active)).toBe(false);
  });

  it('reports whether a document has had its files fetched', () => {
    const nodes = buildSectionsTree(projects, {
      workspaceId: 'ws-1',
      openSlug: 'materiaux',
      trees: { materiaux: tree({ slug: 'materiaux' }) },
    });
    const open = nodes.find((node) => node.slug === 'materiaux');
    const other = nodes.find((node) => node.slug === 'zebra-document');
    expect(open?.filesLoaded).toBe(true);
    expect(open?.files.map((node) => node.name)).toEqual(['assets', 'document.html', 'project.json']);
    expect(other?.filesLoaded).toBe(false);
    expect(other?.files).toEqual([]);
  });

  it('skips a malformed project rather than rendering a blank row', () => {
    const nodes = buildSectionsTree([project({ slug: '' }), project({ slug: 'ok', title: 'Ok' })], {
      workspaceId: 'ws-1',
    });
    expect(nodes.map((node) => node.slug)).toEqual(['ok']);
  });

  it('still lists the open document when the project list omitted it', () => {
    const nodes = buildSectionsTree([], {
      workspaceId: 'ws-1',
      openSlug: 'untitled-mtrrlh2f',
      openTitle: 'Me présenter Sylvain Fréon',
    });
    expect(nodes.map((node) => node.slug)).toEqual(['untitled-mtrrlh2f']);
    expect(nodes[0]?.label).toBe('Me présenter Sylvain Fréon');
    expect(nodes[0]?.active).toBe(true);
  });

  it('does not duplicate the open document when the list already has it', () => {
    const nodes = buildSectionsTree(projects, {
      workspaceId: 'ws-1',
      openSlug: 'materiaux',
      openTitle: 'Should not replace',
    });
    expect(nodes.filter((node) => node.slug === 'materiaux')).toHaveLength(1);
    expect(nodes.find((node) => node.slug === 'materiaux')?.label).toBe(
      'Matériaux de construction',
    );
  });
});

describe('initialExpandedDocuments', () => {
  it('opens the document being edited', () => {
    expect(initialExpandedDocuments('materiaux')).toEqual(['materiaux']);
  });

  it('leaves the tree folded when no document is open', () => {
    expect(initialExpandedDocuments(null)).toEqual([]);
  });
});
