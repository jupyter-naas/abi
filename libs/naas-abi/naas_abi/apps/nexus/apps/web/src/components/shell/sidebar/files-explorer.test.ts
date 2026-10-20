import { describe, expect, it } from 'vitest';
import type { FileInfo } from '@/stores/files';
import {
  canDropOntoExplorerFolder,
  explorerAncestorPaths,
  explorerDirKey,
  explorerDirsToOpen,
  explorerDriveMatchesQuery,
  explorerEntries,
  explorerFolderEntries,
  explorerListQuery,
  explorerLoadedSubtreeMatches,
  explorerParentPath,
  explorerPathAfterMove,
  explorerPathEqualsOrUnder,
  filterExplorerEntriesByQuery,
  isExplorerPathSelected,
  isValidExplorerEntryName,
  matchesExplorerQuery,
  normalizeExplorerPath,
} from './files-explorer';

describe('normalizeExplorerPath', () => {
  it('strips slashes and treats empty as root', () => {
    expect(normalizeExplorerPath('/a/b/')).toBe('a/b');
    expect(normalizeExplorerPath('')).toBe('');
    expect(normalizeExplorerPath('///')).toBe('');
  });
});

describe('explorerParentPath', () => {
  it('returns the parent directory or root', () => {
    expect(explorerParentPath('a/b/c')).toBe('a/b');
    expect(explorerParentPath('icon-check')).toBe('');
    expect(explorerParentPath('')).toBe('');
  });
});

describe('explorerPathEqualsOrUnder', () => {
  it('matches self and descendants', () => {
    expect(explorerPathEqualsOrUnder('docs', 'docs')).toBe(true);
    expect(explorerPathEqualsOrUnder('docs/sub', 'docs')).toBe(true);
    expect(explorerPathEqualsOrUnder('docs', 'images')).toBe(false);
    expect(explorerPathEqualsOrUnder('docs-extra', 'docs')).toBe(false);
  });
});

describe('canDropOntoExplorerFolder', () => {
  it('allows a real move into another folder', () => {
    expect(canDropOntoExplorerFolder('docs/a', 'images')).toBe(true);
    expect(canDropOntoExplorerFolder('a', 'b/c')).toBe(true);
  });

  it('rejects self, current parent, and descendants', () => {
    expect(canDropOntoExplorerFolder('docs/a', 'docs/a')).toBe(false);
    expect(canDropOntoExplorerFolder('docs/a', 'docs')).toBe(false);
    expect(canDropOntoExplorerFolder('docs', 'docs/sub')).toBe(false);
    expect(canDropOntoExplorerFolder('', 'docs')).toBe(false);
  });
});

describe('explorerPathAfterMove', () => {
  it('rewrites the open path when it is under the moved folder', () => {
    expect(explorerPathAfterMove('docs/a', 'docs/a', 'images/a')).toBe('images/a');
    expect(explorerPathAfterMove('docs/a/b', 'docs/a', 'images/a')).toBe('images/a/b');
    expect(explorerPathAfterMove('other', 'docs/a', 'images/a')).toBe(null);
  });
});

describe('isValidExplorerEntryName', () => {
  it('rejects empty names and path separators', () => {
    expect(isValidExplorerEntryName('icon-check')).toBe(true);
    expect(isValidExplorerEntryName('  ')).toBe(false);
    expect(isValidExplorerEntryName('a/b')).toBe(false);
    expect(isValidExplorerEntryName('a\\b')).toBe(false);
    expect(isValidExplorerEntryName('.')).toBe(false);
    expect(isValidExplorerEntryName('..')).toBe(false);
  });
});

describe('explorerDirKey', () => {
  it('joins source and normalized path', () => {
    expect(explorerDirKey('workspace', '/docs/')).toBe('workspace::docs');
    expect(explorerDirKey('my-drive', '')).toBe('my-drive::');
  });
});

describe('explorerAncestorPaths', () => {
  it('returns each prefix including the leaf', () => {
    expect(explorerAncestorPaths('a/b/c')).toEqual(['a', 'a/b', 'a/b/c']);
    expect(explorerAncestorPaths('')).toEqual([]);
  });
});

describe('explorerDirsToOpen', () => {
  it('opens drive root listing and in-drive parents only', () => {
    const root = 'naas_abi/workspace-drive/ws-1';
    expect(explorerDirsToOpen(`${root}/docs/sub`, root)).toEqual([
      '',
      `${root}/docs`,
    ]);
    expect(explorerDirsToOpen(`${root}/docs`, root)).toEqual(['']);
    expect(explorerDirsToOpen(root, root)).toEqual(['']);
    expect(explorerDirsToOpen('', root)).toEqual(['']);
  });
});

describe('explorerFolderEntries', () => {
  it('keeps folders only and sorts by name', () => {
    const files: FileInfo[] = [
      { name: 'z.txt', path: 'z.txt', type: 'file' },
      { name: 'Beta', path: 'Beta', type: 'folder' },
      { name: 'alpha', path: 'alpha', type: 'folder' },
    ];
    expect(explorerFolderEntries(files).map((f) => f.name)).toEqual(['alpha', 'Beta']);
  });
});

describe('explorerEntries', () => {
  it('lists folders then files, each name-sorted', () => {
    const files: FileInfo[] = [
      { name: 'z.txt', path: 'z.txt', type: 'file' },
      { name: 'Beta', path: 'Beta', type: 'folder' },
      { name: 'a.json', path: 'a.json', type: 'file' },
      { name: 'alpha', path: 'alpha', type: 'folder' },
    ];
    expect(explorerEntries(files).map((f) => f.name)).toEqual([
      'alpha',
      'Beta',
      'a.json',
      'z.txt',
    ]);
  });
});

describe('isExplorerPathSelected', () => {
  it('requires matching source and path', () => {
    expect(isExplorerPathSelected('docs', 'docs', 'workspace', 'workspace')).toBe(true);
    expect(isExplorerPathSelected('docs', 'docs', 'workspace', 'my-drive')).toBe(false);
    expect(isExplorerPathSelected('', '', 'workspace', 'workspace')).toBe(true);
    expect(
      isExplorerPathSelected('docs', 'naas_abi/workspace-drive/w/docs', 'workspace', 'workspace'),
    ).toBe(true);
  });
});

describe('explorerListQuery', () => {
  it('builds scope and workspace params', () => {
    expect(explorerListQuery('docs', 'workspace', 'ws-1')).toBe(
      'path=docs&scope=workspace&workspace_id=ws-1',
    );
    expect(explorerListQuery('', 'my-drive', 'ws-1')).toBe('path=&scope=my_drive');
  });
});

describe('matchesExplorerQuery', () => {
  it('matches case-insensitively; empty query matches all', () => {
    expect(matchesExplorerQuery('icon-check', '')).toBe(true);
    expect(matchesExplorerQuery('icon-check', '  ')).toBe(true);
    expect(matchesExplorerQuery('icon-check', 'ICON')).toBe(true);
    expect(matchesExplorerQuery('icon-check', 'images')).toBe(false);
  });
});

describe('filterExplorerEntriesByQuery', () => {
  const root: FileInfo[] = [
    { name: 'images', path: 'images', type: 'folder' },
    { name: 'notes.txt', path: 'notes.txt', type: 'file' },
    { name: 'icon-check', path: 'icon-check', type: 'folder' },
  ];

  it('returns folders then files when query is empty', () => {
    expect(filterExplorerEntriesByQuery(root, '', 'my-drive', {}).map((f) => f.name)).toEqual([
      'icon-check',
      'images',
      'notes.txt',
    ]);
  });

  it('filters by folder or file name without fetching', () => {
    expect(
      filterExplorerEntriesByQuery(root, 'icon', 'my-drive', {}).map((f) => f.name),
    ).toEqual(['icon-check']);
    expect(
      filterExplorerEntriesByQuery(root, 'notes', 'my-drive', {}).map((f) => f.name),
    ).toEqual(['notes.txt']);
  });

  it('keeps ancestors when a loaded descendant folder or file matches', () => {
    const cache = {
      [explorerDirKey('my-drive', 'images')]: [
        { name: 'icon-check', path: 'images/icon-check', type: 'folder' as const },
        { name: 'recent_events.json', path: 'images/recent_events.json', type: 'file' as const },
      ],
    };
    expect(
      filterExplorerEntriesByQuery(root, 'icon-check', 'my-drive', cache).map((f) => f.name),
    ).toEqual(['icon-check', 'images']);
    expect(
      filterExplorerEntriesByQuery(root, 'recent_events', 'my-drive', cache).map((f) => f.name),
    ).toEqual(['images']);
  });
});

describe('explorerLoadedSubtreeMatches', () => {
  it('only inspects cached listings and matches files', () => {
    expect(explorerLoadedSubtreeMatches('my-drive', '', 'x', {})).toBe(false);
    const cache = {
      [explorerDirKey('my-drive', '')]: [
        { name: 'images', path: 'images', type: 'folder' as const },
        { name: 'readme.md', path: 'readme.md', type: 'file' as const },
      ],
    };
    expect(explorerLoadedSubtreeMatches('my-drive', '', 'images', cache)).toBe(true);
    expect(explorerLoadedSubtreeMatches('my-drive', '', 'readme', cache)).toBe(true);
    expect(explorerLoadedSubtreeMatches('my-drive', '', 'missing', cache)).toBe(false);
  });
});

describe('explorerDriveMatchesQuery', () => {
  it('matches drive label or loaded entry names', () => {
    expect(explorerDriveMatchesQuery('My Drive', 'my-drive', 'my', {})).toBe(true);
    expect(explorerDriveMatchesQuery('My Drive', 'my-drive', 'zzz', {})).toBe(false);
    const cache = {
      [explorerDirKey('my-drive', '')]: [
        { name: 'icon-check', path: 'icon-check', type: 'folder' as const },
        { name: 'notes.txt', path: 'notes.txt', type: 'file' as const },
      ],
    };
    expect(explorerDriveMatchesQuery('My Drive', 'my-drive', 'icon', cache)).toBe(true);
    expect(explorerDriveMatchesQuery('My Drive', 'my-drive', 'notes', cache)).toBe(true);
  });
});
