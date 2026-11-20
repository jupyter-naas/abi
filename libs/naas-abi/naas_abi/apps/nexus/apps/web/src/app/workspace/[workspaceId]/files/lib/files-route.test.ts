import { describe, expect, it } from 'vitest';

import {
  filesBrowseHref,
  filesNavigationFromUrl,
  filesStateFromUrl,
  filesNavigationQuery,
  filesUrlKey,
  filesUrlQuery,
  filesUrlSearch,
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
    expect(parseFilesDeepLink(`?source=platform-files&path=${FILE}`)).toEqual({
      source: 'platform-files',
      path: FILE,
    });
  });

  it('reads a query string without a leading question mark', () => {
    expect(parseFilesDeepLink('source=my-files&path=uploads/notes.md')).toEqual({
      source: 'my-files',
      path: 'uploads/notes.md',
    });
  });

  it('trims whitespace on source and path', () => {
    expect(parseFilesDeepLink('?source=  platform-files  &path=  shared/docs  ')).toEqual({
      source: 'platform-files',
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
      source: 'platform-files',
      path: null,
    });
  });

  it.each([
    ['my-drive', 'my-files'],
    ['workspace', 'workspace-files'],
    ['organization-drive', 'organization-files'],
    ['platform-drive', 'platform-files'],
    ['system-drive', 'system-files'],
  ])('opens an old ?source=%s link in %s', (old, view) => {
    expect(parseFilesDeepLink(`?source=${old}&path=docs`)).toEqual({ source: view, path: 'docs' });
  });

  it('ignores a source that names no view (a synced folder of old)', () => {
    expect(parseFilesDeepLink('?source=synced-1&path=docs')).toEqual({ source: null, path: 'docs' });
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

describe('filesStateFromUrl', () => {
  it('opens the default on a bare /files: All Drives, All Views, Workspace Files open', () => {
    expect(filesStateFromUrl('')).toEqual({ drive: 'all', view: 'all', source: 'workspace-files', path: '' });
    expect(filesStateFromUrl('?unrelated=1')).toEqual({ drive: 'all', view: 'all', source: 'workspace-files', path: '' });
  });

  it('reads drive, view, source and path', () => {
    expect(
      filesStateFromUrl('?drive=file_system&view=all&source=my-files&path=naas_abi/my-drive/u/documents'),
    ).toEqual({ drive: 'file_system', view: 'all', source: 'my-files', path: 'naas_abi/my-drive/u/documents' });
  });

  it('keeps the All Views root when the URL names no open view', () => {
    expect(filesStateFromUrl('?drive=all&view=all')).toEqual({ drive: 'all', view: 'all', source: 'all', path: '' });
  });

  it('opens a chosen view on itself when no source is given', () => {
    expect(filesStateFromUrl('?view=my-files')).toEqual({ drive: 'all', view: 'my-files', source: 'my-files', path: '' });
  });

  it('opens an old ?source=&path= link inside All Views', () => {
    expect(filesStateFromUrl('?source=my-drive&path=docs')).toEqual({ drive: 'all', view: 'all', source: 'my-files', path: 'docs' });
  });

  it('reads unknown values as the defaults', () => {
    expect(filesStateFromUrl('?drive=gdrive&view=nope&source=synced-1')).toEqual({
      drive: 'all',
      view: 'all',
      source: 'all',
      path: '',
    });
  });
});

describe('filesUrlQuery', () => {
  it('writes drive, view, the open view and its folder', () => {
    expect(filesUrlQuery({ drive: 'all', view: 'all', source: 'workspace-files', path: '' })).toBe(
      'drive=all&view=all&source=workspace-files',
    );
    expect(filesUrlQuery({ drive: 'all', view: 'all', source: 'my-files', path: 'naas_abi/my-drive/u/documents' })).toBe(
      'drive=all&view=all&source=my-files&path=naas_abi%2Fmy-drive%2Fu%2Fdocuments',
    );
  });

  it('leaves out the open view at the All Views root', () => {
    expect(filesUrlQuery({ drive: 'all', view: 'all', source: 'all', path: '' })).toBe('drive=all&view=all');
  });

  it('round-trips through filesStateFromUrl', () => {
    const state = { drive: 'file_system', view: 'workspace-files', source: 'workspace-files', path: 'finance/q3' } as const;
    expect(filesStateFromUrl(`?${filesUrlQuery(state)}`)).toEqual(state);
  });
});

describe('filesUrlSearch', () => {
  it('sets the Files keys and keeps the other parameters (density)', () => {
    expect(
      filesUrlSearch('?spacing=compact&path=old&source=my-files', {
        drive: 'all',
        view: 'all',
        source: 'workspace-files',
        path: '',
      }),
    ).toBe('?spacing=compact&drive=all&view=all&source=workspace-files');
  });

  it('drops the preview: the page writes the folder it shows, not the file a link opened', () => {
    expect(
      filesUrlSearch('?drive=all&view=all&source=workspace-files&path=finance&preview=finance/q3.pdf', {
        drive: 'all',
        view: 'all',
        source: 'workspace-files',
        path: 'finance',
      }),
    ).toBe('?drive=all&view=all&source=workspace-files&path=finance');
  });
});

describe('filesUrlKey', () => {
  it('keeps only the Files keys and the preview, in one order', () => {
    expect(filesUrlKey('?spacing=compact&path=finance&source=workspace-files&view=all&drive=all')).toBe(
      'drive=all&view=all&source=workspace-files&path=finance',
    );
    expect(filesUrlKey('drive=all&view=all&preview=a.pdf&spacing=cozy')).toBe('drive=all&view=all&preview=a.pdf');
  });

  it('is empty for a bare /files or a URL with other parameters only', () => {
    expect(filesUrlKey('')).toBe('');
    expect(filesUrlKey('?spacing=compact')).toBe('');
  });
});

describe('filesNavigationQuery', () => {
  it('opens a view inside All Views when All Views is the choice', () => {
    expect(
      filesNavigationQuery({ activeDrive: 'all', viewChoice: 'all' }, { source: 'workspace-files', path: '/finance/q3/' }),
    ).toBe('drive=all&view=all&source=workspace-files&path=finance%2Fq3');
  });

  it('makes the view the choice when one view is chosen', () => {
    expect(
      filesNavigationQuery({ activeDrive: 'all', viewChoice: 'my-files' }, { source: 'workspace-files', path: '' }),
    ).toBe('drive=all&view=workspace-files&source=workspace-files');
  });

  it('reads an old drive source as the view it became', () => {
    expect(filesNavigationQuery({ activeDrive: 'all', viewChoice: 'all' }, { source: 'workspace', path: 'hr' })).toBe(
      'drive=all&view=all&source=workspace-files&path=hr',
    );
  });

  it('is the query the page reads back as the same navigation', () => {
    const query = filesNavigationQuery({ activeDrive: 'all', viewChoice: 'all' }, { source: 'platform-files', path: 'shared/docs' });
    expect(filesStateFromUrl(query)).toEqual({ drive: 'all', view: 'all', source: 'platform-files', path: 'shared/docs' });
  });
});

describe('filesNavigationFromUrl', () => {
  it('opens a folder whose name has a dot as a folder (written URLs)', () => {
    expect(filesNavigationFromUrl('?drive=all&view=all&source=workspace-files&path=finance/2024.01')).toEqual({
      state: { drive: 'all', view: 'all', source: 'workspace-files', path: 'finance/2024.01' },
      folderPath: 'finance/2024.01',
      previewPath: null,
    });
  });

  it('previews the file a link names with `preview`', () => {
    expect(
      filesNavigationFromUrl('?drive=all&view=all&source=workspace-files&path=finance&preview=finance/q3.pdf'),
    ).toMatchObject({ folderPath: 'finance', previewPath: 'finance/q3.pdf' });
  });

  it('still reads an old ?source=&path= link to a file as its folder plus a preview', () => {
    expect(filesNavigationFromUrl('?source=workspace&path=finance/q3.pdf')).toMatchObject({
      state: { view: 'all', source: 'workspace-files' },
      folderPath: 'finance',
      previewPath: 'finance/q3.pdf',
    });
  });
});
