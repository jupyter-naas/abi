import { describe, expect, it } from 'vitest';
import type { SlidesProjectTree } from '@/components/shell/sidebar/slides-tree';
import {
  flattenSlidesComposerFiles,
  slidesComposerFallbackFiles,
  slidesComposerFiles,
  slidesComposerRuntimeSuffix,
} from './slides-composer-model';

function tree(over: Partial<SlidesProjectTree> = {}): SlidesProjectTree {
  return {
    slug: 'untitled-mtrv99t1',
    root: 'slides/ws/untitled-mtrv99t1',
    entries: [
      { name: 'deck.html', path: 'slides/untitled-mtrv99t1/deck.html', type: 'file' },
      { name: 'project.json', path: 'slides/untitled-mtrv99t1/project.json', type: 'file' },
      { name: 'assets', path: 'slides/untitled-mtrv99t1/assets', type: 'dir' },
    ],
    assets: [{ name: 'logo.png', path: 'slides/untitled-mtrv99t1/assets/logo.png', type: 'file' }],
    ...over,
  };
}

describe('flattenSlidesComposerFiles', () => {
  it('counts files only, including nested assets', () => {
    const files = slidesComposerFiles(tree());
    expect(files.map((file) => file.name)).toEqual(['logo.png', 'deck.html', 'project.json']);
    expect(files).toHaveLength(3);
  });

  it('marks deck.html as the open file', () => {
    const files = slidesComposerFiles(tree());
    expect(files.find((file) => file.name === 'deck.html')?.open).toBe(true);
    expect(files.find((file) => file.name === 'project.json')?.open).toBe(false);
  });

  it('walks a pre-built node list', () => {
    expect(
      flattenSlidesComposerFiles([
        {
          name: 'assets',
          path: 'slides/x/assets',
          type: 'dir',
          open: false,
          children: [
            { name: 'logo.png', path: 'slides/x/assets/logo.png', type: 'file', open: false, children: [] },
          ],
        },
        { name: 'deck.html', path: 'slides/x/deck.html', type: 'file', open: true, children: [] },
      ]),
    ).toEqual([
      { name: 'logo.png', path: 'slides/x/assets/logo.png', open: false },
      { name: 'deck.html', path: 'slides/x/deck.html', open: true },
    ]);
  });
});

describe('slidesComposerFiles', () => {
  it('falls back to the open deck path before the tree is fetched', () => {
    expect(slidesComposerFiles(null, 'slides/untitled-mtrv99t1/deck.html')).toEqual([
      { name: 'deck.html', path: 'slides/untitled-mtrv99t1/deck.html', open: true },
    ]);
  });

  it('does not invent project.json when the tree is missing', () => {
    expect(slidesComposerFallbackFiles('slides/untitled-mtrv99t1/deck.html')).toEqual([
      { name: 'deck.html', path: 'slides/untitled-mtrv99t1/deck.html', open: true },
    ]);
  });

  it('uses the fetched list even when it is empty', () => {
    expect(
      slidesComposerFiles(
        tree({ entries: [], assets: [] }),
        'slides/untitled-mtrv99t1/deck.html',
      ),
    ).toEqual([]);
  });
});

describe('slidesComposerRuntimeSuffix', () => {
  it('labels a ready workspace and a Forgejo fallback', () => {
    expect(slidesComposerRuntimeSuffix('ready')).toBe('workspace');
    expect(slidesComposerRuntimeSuffix('error')).toBe('Forgejo fallback');
    expect(slidesComposerRuntimeSuffix('degraded')).toBe('Forgejo fallback');
    expect(slidesComposerRuntimeSuffix('ensuring')).toBe('');
    expect(slidesComposerRuntimeSuffix(null)).toBe('');
  });
});
