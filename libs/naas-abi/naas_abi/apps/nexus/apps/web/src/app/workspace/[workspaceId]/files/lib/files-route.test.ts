import { describe, expect, it } from 'vitest';

import {
  filesBrowseHref,
  filesBrowsePath,
  filesDeepLinkFolderAndPreview,
  hasFilesDeepLink,
  matchListedFile,
  parseFilesDeepLink,
  parseFilesRoute,
  stripPlatformDrivePrefix,
} from './files-route';

const WS = 'ws-1';
const BASE = `/workspace/${WS}/files`;
const FILE = 'shared/Organization/External/acme/deck.pptx';
const FOLDER = 'shared/Organization/External/acme';

describe('parseFilesRoute', () => {
  it('shows the drive list on the bare files route', () => {
    expect(parseFilesRoute(BASE)).toEqual({
      isFilesRoute: true,
      isBrowse: false,
    });
  });

  it('opens the file browser on /files/browse', () => {
    expect(parseFilesRoute(`${BASE}/browse`)).toEqual({
      isFilesRoute: true,
      isBrowse: true,
    });
  });

  it('ignores a trailing slash on the index', () => {
    expect(parseFilesRoute(`${BASE}/`).isBrowse).toBe(false);
    expect(parseFilesRoute(`${BASE}/browse/`).isBrowse).toBe(true);
  });

  it('stops at a query string or fragment', () => {
    expect(parseFilesRoute(`${BASE}/browse?path=foo`).isBrowse).toBe(true);
    expect(parseFilesRoute(`${BASE}/browse#top`).isBrowse).toBe(true);
  });

  it('does not claim routes that merely contain the word files', () => {
    expect(parseFilesRoute(`/workspace/${WS}/chat`).isFilesRoute).toBe(false);
    expect(parseFilesRoute(`/workspace/${WS}/fileshare`).isFilesRoute).toBe(false);
  });

  it('treats a missing pathname as no route at all', () => {
    expect(parseFilesRoute(null).isFilesRoute).toBe(false);
    expect(parseFilesRoute(undefined).isFilesRoute).toBe(false);
  });
});

describe('filesBrowsePath', () => {
  it('points at the browse detail inside the workspace', () => {
    expect(filesBrowsePath(WS)).toBe(`${BASE}/browse`);
  });

  it('degrades to a workspace-less path before a workspace is known', () => {
    expect(filesBrowsePath(null)).toBe('/files/browse');
  });
});

describe('filesBrowseHref', () => {
  it('appends a query string to the browse path', () => {
    expect(filesBrowseHref(WS, 'source=platform-drive&path=shared/docs')).toBe(
      `${BASE}/browse?source=platform-drive&path=shared/docs`,
    );
  });

  it('accepts a leading question mark', () => {
    expect(filesBrowseHref(WS, '?source=workspace')).toBe(`${BASE}/browse?source=workspace`);
  });

  it('omits an empty query', () => {
    expect(filesBrowseHref(WS, '')).toBe(`${BASE}/browse`);
    expect(filesBrowseHref(WS, '?')).toBe(`${BASE}/browse`);
  });
});

describe('parseFilesDeepLink', () => {
  it('reads source and a drive-relative path', () => {
    expect(parseFilesDeepLink(`?source=platform-drive&path=${FILE}`)).toEqual({
      source: 'platform-drive',
      path: FILE,
    });
  });

  it('reads a query string without a leading question mark', () => {
    expect(parseFilesDeepLink('source=my-drive&path=uploads/notes.md')).toEqual({
      source: 'my-drive',
      path: 'uploads/notes.md',
    });
  });

  it('trims whitespace on source and path', () => {
    expect(parseFilesDeepLink('?source=  platform-drive  &path=  shared/docs  ')).toEqual({
      source: 'platform-drive',
      path: 'shared/docs',
    });
  });

  it('strips a storage-root prefix from path', () => {
    expect(
      parseFilesDeepLink(
        '?source=platform-drive&path=naas_abi/platform-drive/shared/docs/deck.pptx',
      ).path,
    ).toBe('shared/docs/deck.pptx');
  });

  it('strips a bare platform-drive prefix from path', () => {
    expect(
      parseFilesDeepLink('?source=platform-drive&path=platform-drive/shared/docs/deck.pptx').path,
    ).toBe('shared/docs/deck.pptx');
  });

  it('keeps source when path is omitted', () => {
    expect(parseFilesDeepLink('?source=platform-drive')).toEqual({
      source: 'platform-drive',
      path: null,
    });
  });

  it('keeps path when source is omitted', () => {
    expect(parseFilesDeepLink('?path=shared/docs')).toEqual({
      source: null,
      path: 'shared/docs',
    });
  });

  it('returns empty fields when the query is missing or blank', () => {
    expect(parseFilesDeepLink(null)).toEqual({ source: null, path: null });
    expect(parseFilesDeepLink('')).toEqual({ source: null, path: null });
    expect(parseFilesDeepLink('?source=&path=')).toEqual({ source: null, path: null });
  });

  it('decodes a percent-encoded path', () => {
    expect(parseFilesDeepLink('?path=shared%2FMy%20Deck.pptx').path).toBe('shared/My Deck.pptx');
  });
});

describe('hasFilesDeepLink', () => {
  it('is true when source or path is present', () => {
    expect(hasFilesDeepLink('?source=platform-drive')).toBe(true);
    expect(hasFilesDeepLink('?path=shared/docs')).toBe(true);
  });

  it('is false when both fields are empty', () => {
    expect(hasFilesDeepLink(null)).toBe(false);
    expect(hasFilesDeepLink('?source=&path=')).toBe(false);
  });
});

describe('filesDeepLinkFolderAndPreview', () => {
  it('opens a file by listing its folder and previewing the file', () => {
    expect(filesDeepLinkFolderAndPreview(FILE)).toEqual({
      folderPath: FOLDER,
      previewPath: FILE,
    });
  });

  it('treats a folder path as browse-only', () => {
    expect(filesDeepLinkFolderAndPreview(FOLDER)).toEqual({
      folderPath: FOLDER,
    });
  });

  it('previews a file at the drive root', () => {
    expect(filesDeepLinkFolderAndPreview('deck.pptx')).toEqual({
      folderPath: '',
      previewPath: 'deck.pptx',
    });
  });

  it('strips a storage-root prefix before splitting', () => {
    expect(
      filesDeepLinkFolderAndPreview('naas_abi/platform-drive/shared/docs/deck.pptx'),
    ).toEqual({
      folderPath: 'shared/docs',
      previewPath: 'shared/docs/deck.pptx',
    });
  });

  it('treats an empty or prefix-only path as the drive root', () => {
    expect(filesDeepLinkFolderAndPreview('')).toEqual({ folderPath: '' });
    expect(filesDeepLinkFolderAndPreview('naas_abi/platform-drive')).toEqual({ folderPath: '' });
  });
});

describe('stripPlatformDrivePrefix', () => {
  it('leaves a drive-relative path unchanged', () => {
    expect(stripPlatformDrivePrefix('shared/docs/deck.pptx')).toBe('shared/docs/deck.pptx');
  });

  it('trims leading and trailing slashes', () => {
    expect(stripPlatformDrivePrefix('/shared/docs/')).toBe('shared/docs');
  });
});

describe('matchListedFile', () => {
  const listed = [
    {
      name: 'deck.pptx',
      path: 'naas_abi/platform-drive/shared/Organization/External/acme/deck.pptx',
    },
    { name: 'notes.md', path: 'naas_abi/platform-drive/shared/docs/notes.md' },
  ];

  it('matches a drive-relative preview to a full storage-key listing', () => {
    expect(matchListedFile(listed, FILE)?.name).toBe('deck.pptx');
  });

  it('matches an exact storage-key preview', () => {
    expect(matchListedFile(listed, listed[1].path)?.name).toBe('notes.md');
  });

  it('matches by file name when the prefix differs', () => {
    expect(matchListedFile(listed, 'deck.pptx')?.name).toBe('deck.pptx');
  });

  it('returns undefined when nothing matches', () => {
    expect(matchListedFile(listed, 'missing/report.pdf')).toBeUndefined();
  });
});
