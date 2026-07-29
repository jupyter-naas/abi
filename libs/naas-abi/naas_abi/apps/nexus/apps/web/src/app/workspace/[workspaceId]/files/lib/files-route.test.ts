import { describe, expect, it } from 'vitest';

import { filesBrowsePath, parseFilesRoute } from './files-route';

const WS = 'ws-1';
const BASE = `/workspace/${WS}/files`;

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
