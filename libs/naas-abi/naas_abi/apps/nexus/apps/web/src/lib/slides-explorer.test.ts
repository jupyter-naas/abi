import { describe, expect, it } from 'vitest';

import {
  buildSlidesExplorer,
  curateAssetEntries,
  curateProjectEntries,
  entryBasename,
  isNoiseName,
  isUnderProjectRoot,
} from './slides-explorer';
import type { SlidesSeedTemplate } from './slides-templates';

const LIGHT: SlidesSeedTemplate = {
  id: 'minimal-light-v1',
  name: 'Minimal Light',
  description: '',
  preview_bg: '#f7f6f3',
  preview_panel: '#ffffff',
  preview_accent: '#1a1a1a',
  preview_ink: '#1a1a1a',
  slides: [{ index: 0, eyebrow: 'Agenda', title: 'What we will cover' }],
  assets: [
    { name: 'hero', kind: 'embedded' },
    { name: 'logo', kind: 'embedded' },
  ],
  files: [{ name: 'deck.html', kind: 'html' }],
};

describe('entryBasename', () => {
  it('strips nested InMemory paths', () => {
    expect(entryBasename('slides/ws-abc/untitled-1/deck.html')).toBe('deck.html');
    expect(entryBasename('deck.html', 'slides/ws-abc/untitled-1/deck.html')).toBe('deck.html');
  });
});

describe('isNoiseName', () => {
  it('hides hashes, workspace ids, and sidecar folders', () => {
    expect(isNoiseName('a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2')).toBe(true);
    expect(isNoiseName('ws-4053737115ad')).toBe(true);
    expect(isNoiseName('.coder')).toBe(true);
    expect(isNoiseName('.gitkeep')).toBe(true);
    expect(isNoiseName('deck.html')).toBe(false);
  });
});

describe('isUnderProjectRoot', () => {
  it('keeps only this presentation folder', () => {
    const root = 'slides/ws-test/untitled-local';
    expect(isUnderProjectRoot(`${root}/deck.html`, root)).toBe(true);
    expect(isUnderProjectRoot('slides/ws-other/other/deck.html', root)).toBe(false);
    expect(isUnderProjectRoot('README.md', root)).toBe(false);
  });
});

describe('curateProjectEntries', () => {
  it('normalizes an InMemory dump to project root files', () => {
    const root = 'slides/ws-test/untitled-local';
    const entries = curateProjectEntries(
      [
        { name: 'README.md', path: 'README.md', type: 'file' },
        {
          name: `${root}/deck.html`,
          path: `${root}/deck.html`,
          type: 'file',
        },
        {
          name: `${root}/project.json`,
          path: `${root}/project.json`,
          type: 'file',
        },
        {
          name: 'slides/ws-other/other/deck.html',
          path: 'slides/ws-other/other/deck.html',
          type: 'file',
        },
        { name: '.coder', path: '.coder', type: 'dir' },
      ],
      root,
    );
    expect(entries.map((e) => e.name)).toEqual(['assets', 'deck.html', 'project.json']);
    expect(entries.every((e) => !e.name.includes('/'))).toBe(true);
  });
});

describe('curateAssetEntries', () => {
  it('keeps downloaded files and hides folder bookkeeping', () => {
    const dir = 'slides/ws-test/untitled-local/assets';
    const assets = curateAssetEntries(
      [
        { name: `${dir}/.gitkeep`, path: `${dir}/.gitkeep`, type: 'file' },
        { name: `${dir}/README.md`, path: `${dir}/README.md`, type: 'file' },
        { name: `${dir}/hero.svg`, path: `${dir}/hero.svg`, type: 'file' },
        {
          name: 'slides/ws-other/other/assets/skip.png',
          path: 'slides/ws-other/other/assets/skip.png',
          type: 'file',
        },
      ],
      dir,
    );
    expect(assets.map((a) => a.name)).toEqual(['hero.svg']);
  });
});

describe('buildSlidesExplorer', () => {
  it('builds an IDE tree with templates, deck files, and an assets folder', () => {
    const tree = buildSlidesExplorer({
      projectTitle: 'Hormuz brief',
      projectSlug: 'untitled-local',
      projectRoot: 'slides/ws-test/untitled-local',
      tree: {
        slug: 'untitled-local',
        root: 'slides/ws-test/untitled-local',
        entries: [
          { name: 'deck.html', path: 'slides/ws-test/untitled-local/deck.html', type: 'file' },
        ],
        assets: [],
      },
      templates: [LIGHT],
      projects: [
        { slug: 'untitled-local', title: 'Hormuz brief' },
        { slug: 'other-deck', title: 'Other deck' },
      ],
    });
    expect(tree.map((n) => n.name)).toEqual(['Hormuz brief', 'Other deck', 'Templates']);
    const project = tree[0];
    expect(project.renamable).toBe(true);
    expect(project.id).toBe('project:untitled-local');
    expect(project.children?.map((c) => c.name)).toEqual(['deck.html', 'project.json', 'assets']);
    const assets = project.children?.find((c) => c.name === 'assets');
    expect(assets?.emptyLabel).toBe('No images yet');
    expect(tree[1].kind).toBe('folder');
    expect(tree[1].children?.some((c) => c.name === 'deck.html')).toBe(true);
    const template = tree[2].children?.[0];
    expect(template?.name).toBe('Minimal Light');
    expect(template?.children?.map((c) => c.name)).toEqual(['deck.html', 'assets']);
    expect(template?.children?.some((c) => c.name === 'What we will cover')).toBe(false);
    const templateAssets = template?.children?.find((c) => c.name === 'assets');
    expect(templateAssets?.children?.map((c) => c.name)).toEqual(['hero', 'logo']);
  });
});
