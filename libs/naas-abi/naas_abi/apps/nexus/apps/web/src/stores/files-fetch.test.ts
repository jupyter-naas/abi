import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.hoisted(() => vi.fn());
vi.mock('./auth', () => ({ authFetch }));
vi.mock('@/lib/config', () => ({ getApiUrl: () => 'http://api' }));
vi.mock('./workspace', () => ({
  useWorkspaceStore: { getState: () => ({ currentWorkspaceId: 'ws-1' }) },
}));

import { invalidateFilesRequests, useFilesStore } from './files';

type Pending = {
  url: string;
  signal?: AbortSignal;
  resolve: (files: string[], total?: number) => void;
  reject: (error: Error) => void;
};

let pending: Pending[] = [];

function listing(names: string[], total = names.length) {
  return {
    ok: true,
    json: async () => ({
      files: names.map((name) => ({ name, path: name, type: 'file' })),
      total,
    }),
  };
}

function pathOf(call: Pending): string {
  return new URL(call.url).searchParams.get('path') ?? '';
}

function names(): string[] {
  return useFilesStore.getState().files.map((f) => f.name);
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
  pending = [];
  authFetch.mockReset();
  authFetch.mockImplementation(
    (url: string, init?: RequestInit) =>
      new Promise((resolve, reject) => {
        pending.push({
          url,
          signal: init?.signal ?? undefined,
          resolve: (files, total) => resolve(listing(files, total)),
          reject,
        });
      }),
  );
  invalidateFilesRequests();
  useFilesStore.setState({
    files: [],
    currentPath: '',
    loading: false,
    error: null,
    activeSource: 'workspace',
    filesTotal: 0,
    filesLimit: null,
    filesOffset: 0,
    filesSearch: '',
  });
});

describe('fetchFiles stale responses', () => {
  it('a slow folder A never replaces the faster folder B', async () => {
    const a = useFilesStore.getState().fetchFiles('A', { workspaceId: 'ws-1' });
    const b = useFilesStore.getState().fetchFiles('B', { workspaceId: 'ws-1' });
    expect(pending.map(pathOf)).toEqual(['A', 'B']);
    expect(pending[0].signal?.aborted).toBe(true);
    expect(pending[1].signal?.aborted).toBe(false);

    pending[1].resolve(['b.txt']);
    await b;
    pending[0].resolve(['a.txt']);
    await a;

    expect(names()).toEqual(['b.txt']);
    expect(useFilesStore.getState().currentPath).toBe('B');
    expect(useFilesStore.getState().loading).toBe(false);
  });

  it('a stale failure or abort cannot set the error or clear loading', async () => {
    const a = useFilesStore.getState().fetchFiles('A', { workspaceId: 'ws-1' });
    const b = useFilesStore.getState().fetchFiles('B', { workspaceId: 'ws-1' });
    pending[0].reject(new DOMException('The user aborted a request.', 'AbortError') as unknown as Error);
    await a;
    expect(useFilesStore.getState().error).toBeNull();
    expect(useFilesStore.getState().loading).toBe(true);

    pending[1].resolve(['b.txt']);
    await b;
    expect(useFilesStore.getState().loading).toBe(false);
    expect(names()).toEqual(['b.txt']);
  });

  it('the current request still reports its own failure', async () => {
    const a = useFilesStore.getState().fetchFiles('A', { workspaceId: 'ws-1' });
    pending[0].reject(new Error('Failed to fetch files'));
    await a;
    expect(useFilesStore.getState().error).toBe('Failed to fetch files');
    expect(useFilesStore.getState().loading).toBe(false);
  });

  it('keeps the latest page when page responses arrive out of order', async () => {
    const page1 = useFilesStore.getState().fetchFiles('A', { workspaceId: 'ws-1', limit: 2, offset: 0 });
    const page2 = useFilesStore.getState().fetchFiles('A', { workspaceId: 'ws-1', limit: 2, offset: 2 });
    pending[1].resolve(['c', 'd'], 4);
    await page2;
    pending[0].resolve(['a', 'b'], 4);
    await page1;
    const state = useFilesStore.getState();
    expect(names()).toEqual(['c', 'd']);
    expect(state.filesOffset).toBe(2);
    expect(state.filesTotal).toBe(4);
  });

  it('switching drive invalidates the pending listing', async () => {
    const a = useFilesStore.getState().fetchFiles('A', { workspaceId: 'ws-1' });
    useFilesStore.getState().setActiveSource('my-drive');
    expect(pending[0].signal?.aborted).toBe(true);
    pending[0].resolve(['workspace.txt']);
    await a;
    expect(names()).toEqual([]);
  });

  it('switching workspace isolates the listing', async () => {
    const one = useFilesStore.getState().fetchFiles('', { workspaceId: 'ws-1' });
    const two = useFilesStore.getState().fetchFiles('', { workspaceId: 'ws-2' });
    expect(new URL(pending[1].url).searchParams.get('workspace_id')).toBe('ws-2');
    pending[1].resolve(['two.txt']);
    await two;
    pending[0].resolve(['one.txt']);
    await one;
    await flush();
    expect(names()).toEqual(['two.txt']);
  });

  it('a stale root listing does not run the workspace-root fallback', async () => {
    const one = useFilesStore.getState().fetchFiles('', { workspaceId: 'ws-1' });
    const two = useFilesStore.getState().fetchFiles('B', { workspaceId: 'ws-1' });
    pending[0].resolve([], 0);
    await one;
    expect(pending).toHaveLength(2);
    pending[1].resolve(['b.txt']);
    await two;
    expect(names()).toEqual(['b.txt']);
  });
});
