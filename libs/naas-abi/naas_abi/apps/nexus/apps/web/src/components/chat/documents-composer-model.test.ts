import { describe, expect, it } from 'vitest';
import type { DocumentsProjectTree } from '@/components/shell/sidebar/documents-tree';
import {
  flattenSectionsComposerFiles,
  sectionsComposerFallbackFiles,
  sectionsComposerFiles,
} from './documents-composer-model';

function tree(over: Partial<DocumentsProjectTree> = {}): DocumentsProjectTree {
  return {
    slug: 'untitled-mtrv99t1',
    root: 'documents/ws/untitled-mtrv99t1',
    entries: [
      { name: 'document.html', path: 'documents/untitled-mtrv99t1/document.html', type: 'file' },
      { name: 'project.json', path: 'documents/untitled-mtrv99t1/project.json', type: 'file' },
      { name: 'assets', path: 'documents/untitled-mtrv99t1/assets', type: 'dir' },
    ],
    assets: [{ name: 'logo.png', path: 'documents/untitled-mtrv99t1/assets/logo.png', type: 'file' }],
    ...over,
  };
}

describe('flattenSectionsComposerFiles', () => {
  it('counts files only, including nested assets', () => {
    const files = sectionsComposerFiles(tree());
    expect(files.map((file) => file.name)).toEqual(['logo.png', 'document.html', 'project.json']);
    expect(files).toHaveLength(3);
  });

  it('marks document.html as the open file', () => {
    const files = sectionsComposerFiles(tree());
    expect(files.find((file) => file.name === 'document.html')?.open).toBe(true);
    expect(files.find((file) => file.name === 'project.json')?.open).toBe(false);
  });

  it('walks a pre-built node list', () => {
    expect(
      flattenSectionsComposerFiles([
        {
          name: 'assets',
          path: 'documents/x/assets',
          type: 'dir',
          open: false,
          children: [
            { name: 'logo.png', path: 'documents/x/assets/logo.png', type: 'file', open: false, children: [] },
          ],
        },
        { name: 'document.html', path: 'documents/x/document.html', type: 'file', open: true, children: [] },
      ]),
    ).toEqual([
      { name: 'logo.png', path: 'documents/x/assets/logo.png', open: false },
      { name: 'document.html', path: 'documents/x/document.html', open: true },
    ]);
  });
});

describe('sectionsComposerFiles', () => {
  it('falls back to the open document path before the tree is fetched', () => {
    expect(sectionsComposerFiles(null, 'documents/untitled-mtrv99t1/document.html')).toEqual([
      { name: 'document.html', path: 'documents/untitled-mtrv99t1/document.html', open: true },
    ]);
  });

  it('does not invent project.json when the tree is missing', () => {
    expect(sectionsComposerFallbackFiles('documents/untitled-mtrv99t1/document.html')).toEqual([
      { name: 'document.html', path: 'documents/untitled-mtrv99t1/document.html', open: true },
    ]);
  });

  it('uses the fetched list even when it is empty', () => {
    expect(
      sectionsComposerFiles(
        tree({ entries: [], assets: [] }),
        'documents/untitled-mtrv99t1/document.html',
      ),
    ).toEqual([]);
  });
});
