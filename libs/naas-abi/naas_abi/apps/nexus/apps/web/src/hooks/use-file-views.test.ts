import { describe, expect, it, vi } from 'vitest';

// The workspace store (imported through the views hook) checks the session on a timer.
vi.mock('@/stores/auth', () => ({ authFetch: vi.fn(), hasSession: vi.fn(() => false) }));

import { createFileViewsStore } from './use-file-views';

const MY_FILES = { id: 'my_files', label: 'My Files', drive: 'file_system', scope: 'my_drive', root: 'r' };
const WORKSPACE_FILES = {
  id: 'workspace_files',
  label: 'Workspace Files',
  drive: 'file_system',
  scope: 'workspace',
  root: 'w',
};

const answer = (views: unknown[]) => ({ ok: true, status: 200, json: async () => ({ views }) }) as Response;

describe('the views store', () => {
  it('asks once per workspace, even for two callers at once', async () => {
    const fetcher = vi.fn(async () => answer([MY_FILES]));
    const store = createFileViewsStore(fetcher);
    await Promise.all([store.getState().load('ws-1'), store.getState().load('ws-1')]);
    await store.getState().load('ws-1');
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith('/api/files/views?workspace_id=ws-1');
    expect(store.getState()).toMatchObject({ status: 'ready', workspaceId: 'ws-1' });
    expect(store.getState().views.map((v) => v.id)).toEqual(['my_files']);
  });

  it('asks again for another workspace, or when forced', async () => {
    const fetcher = vi.fn(async (url: string) =>
      answer(url.includes('ws-2') ? [WORKSPACE_FILES] : [MY_FILES]),
    );
    const store = createFileViewsStore(fetcher);
    await store.getState().load('ws-1');
    await store.getState().load('ws-2');
    expect(store.getState().views.map((v) => v.id)).toEqual(['workspace_files']);
    await store.getState().load('ws-2', { force: true });
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it('keeps the last answer when a read fails, and lists nothing without one', async () => {
    const fetcher = vi.fn(async () => answer([MY_FILES]));
    const store = createFileViewsStore(fetcher);
    await store.getState().load('ws-1');
    fetcher.mockImplementationOnce(async () => ({ ok: false, status: 500 }) as Response);
    await store.getState().load('ws-1', { force: true });
    expect(store.getState().views.map((v) => v.id)).toEqual(['my_files']);

    fetcher.mockImplementationOnce(async () => {
      throw new Error('offline');
    });
    await store.getState().load('ws-3');
    expect(store.getState()).toMatchObject({ status: 'error', views: [] });
  });
});
