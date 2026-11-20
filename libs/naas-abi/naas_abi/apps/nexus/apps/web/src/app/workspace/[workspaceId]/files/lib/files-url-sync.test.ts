import { describe, expect, it } from 'vitest';

import { createFilesUrlSync, expectFilesUrl, filesUrlWrite, takeFilesUrl } from './files-url-sync';

const ROOT = 'drive=all&view=all&source=workspace-files';
const FOLDER = 'drive=all&view=all&source=workspace-files&path=finance';
const OTHER = 'drive=all&view=all&source=workspace-files&path=hr';

describe('takeFilesUrl', () => {
  it('applies the first URL of the page load, then not again', () => {
    const sync = createFilesUrlSync();
    expect(takeFilesUrl(sync, ROOT)).toBe(true);
    expect(takeFilesUrl(sync, ROOT)).toBe(false);
  });

  it('applies a URL whose Files keys changed (Back, a link)', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, ROOT);
    expect(takeFilesUrl(sync, FOLDER)).toBe(true);
  });

  it('does not apply a URL again when only other parameters changed (density)', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, FOLDER);
    expect(takeFilesUrl(sync, `${FOLDER}&spacing=compact`)).toBe(false);
    expect(takeFilesUrl(sync, `spacing=cozy&${FOLDER}`)).toBe(false);
  });

  it('takes the URL a navigation pushed as applied once it lands', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, ROOT);
    expectFilesUrl(sync, FOLDER, ROOT);
    expect(takeFilesUrl(sync, FOLDER)).toBe(false);
    expect(sync.expect).toBeNull();
  });

  it('applies another URL than the one a navigation pushed, and stops waiting for it', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, ROOT);
    expectFilesUrl(sync, FOLDER, ROOT);
    expect(takeFilesUrl(sync, OTHER)).toBe(true);
    expect(sync.expect).toBeNull();
    // Back to the pushed URL later is a real change: it is applied.
    expect(takeFilesUrl(sync, FOLDER)).toBe(true);
  });

  it('applies a bare /files after a navigation whose push was discarded', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, FOLDER);
    expectFilesUrl(sync, OTHER, FOLDER);
    expect(takeFilesUrl(sync, '')).toBe(true);
  });
});

describe('expectFilesUrl', () => {
  it('waits for nothing when the navigation pushes no URL (move, rename)', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, ROOT);
    expectFilesUrl(sync, undefined, ROOT);
    expect(sync.expect).toBeNull();
    // A later Back is applied, never swallowed.
    expect(takeFilesUrl(sync, FOLDER)).toBe(true);
  });

  it('waits for nothing when the URL already says where the navigation goes', () => {
    const sync = createFilesUrlSync();
    expectFilesUrl(sync, FOLDER, `${FOLDER}&spacing=compact`);
    expect(sync.expect).toBeNull();
    expect(takeFilesUrl(sync, `${FOLDER}&spacing=compact`)).toBe(false);
  });
});

describe('filesUrlWrite', () => {
  it('writes nothing before the page applied a URL', () => {
    const sync = createFilesUrlSync();
    expect(filesUrlWrite(sync, `?${FOLDER}`, '', false)).toBe(false);
  });

  it('writes nothing while a router navigation is in flight', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, ROOT);
    expect(filesUrlWrite(sync, `?${FOLDER}`, `?${ROOT}`, true)).toBe(false);
    expect(sync.applied).toBe(ROOT);
  });

  it('writes a changed state and records it, so it never comes back as a URL to apply', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, ROOT);
    expect(filesUrlWrite(sync, `?${FOLDER}&spacing=compact`, `?${ROOT}&spacing=compact`, false)).toBe(true);
    expect(takeFilesUrl(sync, `${FOLDER}&spacing=compact`)).toBe(false);
  });

  it('writes nothing when the URL already holds the state', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, ROOT);
    expect(filesUrlWrite(sync, `?${FOLDER}`, `?${FOLDER}`, false)).toBe(false);
    expect(sync.applied).toBe(FOLDER);
  });

  it('writes to drop a stale preview', () => {
    const sync = createFilesUrlSync();
    takeFilesUrl(sync, `${FOLDER}&preview=finance%2Fq3.pdf`);
    expect(filesUrlWrite(sync, `?${FOLDER}`, `?${FOLDER}&preview=finance%2Fq3.pdf`, false)).toBe(true);
    expect(takeFilesUrl(sync, FOLDER)).toBe(false);
  });
});
