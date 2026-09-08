import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.fn();

vi.mock('@/stores/auth', () => ({
  authFetch: (...args: unknown[]) => authFetch(...args),
}));

import {
  copyDeckToMyDrive,
  myDriveCopyErrorMessage,
  myDriveDeckRelativePath,
  myDriveProjectRelativePath,
  myDriveSlidesDir,
} from './slides-my-drive';

describe('My Drive slides paths', () => {
  it('keeps a user-relative slides/<slug> tree', () => {
    expect(myDriveSlidesDir('industry-deck')).toBe('slides/industry-deck');
    expect(myDriveDeckRelativePath('industry-deck')).toBe('slides/industry-deck/deck.html');
    expect(myDriveProjectRelativePath('industry-deck')).toBe(
      'slides/industry-deck/project.json',
    );
  });
});

describe('myDriveCopyErrorMessage', () => {
  it('hides storage internals', () => {
    expect(myDriveCopyErrorMessage('MinIO endpoint refused', 502)).toBe(
      'My Drive is unavailable.',
    );
    expect(myDriveCopyErrorMessage('could not connect to s3 bucket abi', 400)).toBe(
      'Could not copy to My Drive.',
    );
    expect(myDriveCopyErrorMessage('nope', 413)).toBe('Deck is too large for My Drive.');
  });
});

describe('copyDeckToMyDrive', () => {
  beforeEach(() => {
    authFetch.mockReset();
  });

  it('uploads deck.html then project.json with scope my_drive', async () => {
    authFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ path: 'naas_abi/my-drive/user-1/slides/demo/deck.html' }),
    });

    const result = await copyDeckToMyDrive({
      slug: 'demo',
      html: '<html></html>',
      title: 'Demo deck',
      workspaceId: 'ws-1',
    });

    expect(result.relativePath).toBe('slides/demo/deck.html');
    expect(authFetch).toHaveBeenCalledTimes(2);

    const first = authFetch.mock.calls[0] as [string, RequestInit];
    expect(first[0]).toBe('/api/files/upload');
    const form = first[1].body as FormData;
    expect(form.get('path')).toBe('slides/demo');
    expect(form.get('scope')).toBe('my_drive');
    const file = form.get('file') as File;
    expect(file.name).toBe('deck.html');

    const second = authFetch.mock.calls[1] as [string, RequestInit];
    const projectForm = second[1].body as FormData;
    expect((projectForm.get('file') as File).name).toBe('project.json');
  });

  it('still succeeds when project.json upload fails', async () => {
    authFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ path: 'naas_abi/my-drive/user-1/slides/demo/deck.html' }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'MinIO is down' }),
      });

    const result = await copyDeckToMyDrive({
      slug: 'demo',
      html: '<html></html>',
    });
    expect(result.relativePath).toBe('slides/demo/deck.html');
  });
});
