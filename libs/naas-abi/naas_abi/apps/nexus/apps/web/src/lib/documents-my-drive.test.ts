import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.fn();

vi.mock('@/stores/auth', () => ({
  authFetch: (...args: unknown[]) => authFetch(...args),
}));

import {
  copyDocumentToMyDrive,
  myDriveCopyErrorMessage,
  myDriveDocumentRelativePath,
  myDriveProjectRelativePath,
  myDriveSectionsDir,
} from './documents-my-drive';

describe('My Drive sections paths', () => {
  it('keeps a user-relative documents/<slug> tree', () => {
    expect(myDriveSectionsDir('industry-document')).toBe('documents/industry-document');
    expect(myDriveDocumentRelativePath('industry-document')).toBe('documents/industry-document/document.html');
    expect(myDriveProjectRelativePath('industry-document')).toBe(
      'documents/industry-document/project.json',
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
    expect(myDriveCopyErrorMessage('nope', 413)).toBe('Document is too large for My Drive.');
  });
});

describe('copyDocumentToMyDrive', () => {
  beforeEach(() => {
    authFetch.mockReset();
  });

  it('uploads document.html then project.json with scope my_drive', async () => {
    authFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ path: 'naas_abi/my-drive/user-1/documents/demo/document.html' }),
    });

    const result = await copyDocumentToMyDrive({
      slug: 'demo',
      html: '<html></html>',
      title: 'Demo document',
      workspaceId: 'ws-1',
    });

    expect(result.relativePath).toBe('documents/demo/document.html');
    expect(authFetch).toHaveBeenCalledTimes(2);

    const first = authFetch.mock.calls[0] as [string, RequestInit];
    expect(first[0]).toBe('/api/files/upload');
    const form = first[1].body as FormData;
    expect(form.get('path')).toBe('documents/demo');
    expect(form.get('scope')).toBe('my_drive');
    const file = form.get('file') as File;
    expect(file.name).toBe('document.html');

    const second = authFetch.mock.calls[1] as [string, RequestInit];
    const projectForm = second[1].body as FormData;
    expect((projectForm.get('file') as File).name).toBe('project.json');
  });

  it('still succeeds when project.json upload fails', async () => {
    authFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ path: 'naas_abi/my-drive/user-1/documents/demo/document.html' }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'MinIO is down' }),
      });

    const result = await copyDocumentToMyDrive({
      slug: 'demo',
      html: '<html></html>',
    });
    expect(result.relativePath).toBe('documents/demo/document.html');
  });
});
