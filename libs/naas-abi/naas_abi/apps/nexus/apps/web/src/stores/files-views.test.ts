import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.hoisted(() => vi.fn());
vi.mock('./auth', () => ({ authFetch, useAuthStore: { getState: () => ({ view: null }) } }));
vi.mock('@/lib/config', () => ({ getApiUrl: () => 'http://api' }));
vi.mock('./workspace', () => ({
  useWorkspaceStore: { getState: () => ({ currentWorkspaceId: 'ws-1' }) },
}));

import { starredItemsFrom, useFilesStore } from './files';

beforeEach(() => {
  authFetch.mockReset();
  authFetch.mockResolvedValue({ ok: true, json: async () => ({ files: [], total: 0 }) });
  useFilesStore.setState({ activeSource: 'all', viewChoice: 'all', activeDrive: 'all', files: [] });
});

describe('starred items kept with an old source', () => {
  it('open the view that source is now', () => {
    const stored = [
      { path: 'a.md', name: 'a.md', type: 'file', source: 'my-drive', workspaceId: 'ws-1' },
      { path: 'b', name: 'b', type: 'folder', source: 'workspace', workspaceId: 'ws-1' },
      { path: 'c', name: 'c', type: 'folder', source: 'organization-drive', workspaceId: 'ws-1' },
      { path: 'd', name: 'd', type: 'folder', source: 'platform-drive', workspaceId: 'ws-1' },
      { path: 'e', name: 'e', type: 'folder', source: 'system-drive', workspaceId: 'ws-1' },
      { path: 'f', name: 'f', type: 'folder', source: 'workspace-files', workspaceId: 'ws-1' },
    ];
    expect(starredItemsFrom(stored).map((item) => item.source)).toEqual([
      'my-files',
      'workspace-files',
      'organization-files',
      'platform-files',
      'system-files',
      'workspace-files',
    ]);
  });

  it('drop an item of a synced local folder (gone) and anything unreadable', () => {
    const stored = [
      { path: 'x', name: 'x', type: 'file', source: 'synced-1700000000', workspaceId: 'ws-1' },
      'garbage',
      null,
    ];
    expect(starredItemsFrom(stored)).toEqual([]);
    expect(starredItemsFrom({ not: 'a list' })).toEqual([]);
  });
});

describe('the active view', () => {
  it('starts on All Views, under All Drives', () => {
    const state = useFilesStore.getInitialState();
    expect(state.activeSource).toBe('all');
    expect(state.viewChoice).toBe('all');
    expect(state.activeDrive).toBe('all');
  });

  it('reads an old source as its view', () => {
    useFilesStore.getState().setActiveSource('my-drive');
    expect(useFilesStore.getState().activeSource).toBe('my-files');
  });

  it('opens a view from All Views and keeps All Views chosen, so the breadcrumb leads back', () => {
    useFilesStore.getState().setActiveSource('workspace-files');
    expect(useFilesStore.getState().activeSource).toBe('workspace-files');
    expect(useFilesStore.getState().viewChoice).toBe('all');
  });

  it('follows a link to another view when one view is chosen', () => {
    useFilesStore.getState().chooseView('my-files');
    useFilesStore.getState().setActiveSource('platform-files');
    expect(useFilesStore.getState().viewChoice).toBe('platform-files');
  });

  it('choosing a view in the dropdown opens it; All Views goes back to its folders', () => {
    useFilesStore.getState().chooseView('organization-files');
    expect(useFilesStore.getState()).toMatchObject({
      activeSource: 'organization-files',
      viewChoice: 'organization-files',
    });
    useFilesStore.getState().chooseView('all');
    expect(useFilesStore.getState()).toMatchObject({ activeSource: 'all', viewChoice: 'all' });
  });

  it('the dock and Home open Workspace Files inside All Views, whatever was open before', () => {
    useFilesStore.getState().chooseView('my-files');
    useFilesStore.getState().openFilesEntry();
    expect(useFilesStore.getState()).toMatchObject({
      activeSource: 'workspace-files',
      viewChoice: 'all',
    });
  });

  it('ignores a source that names no view', () => {
    useFilesStore.getState().setActiveSource('workspace-files');
    useFilesStore.getState().setActiveSource('synced-1');
    expect(useFilesStore.getState().activeSource).toBe('workspace-files');
  });

  it('asks the API nothing for All Views', async () => {
    useFilesStore.setState({ files: [{ name: 'old', path: 'old', type: 'file' }] });
    await useFilesStore.getState().fetchFiles('', { workspaceId: 'ws-1' });
    expect(authFetch).not.toHaveBeenCalled();
    expect(useFilesStore.getState()).toMatchObject({ files: [], currentPath: '', loading: false });
  });
});

describe('synced local folders', () => {
  it('are gone from the store', () => {
    const state = useFilesStore.getState() as unknown as Record<string, unknown>;
    for (const key of [
      'syncedFolders',
      'syncLocalFolder',
      'addSyncedFolder',
      'removeSyncedFolder',
      'toggleSyncFolder',
      'fetchLocalFiles',
      'storageSources',
    ]) {
      expect(state[key], key).toBeUndefined();
    }
  });
});
