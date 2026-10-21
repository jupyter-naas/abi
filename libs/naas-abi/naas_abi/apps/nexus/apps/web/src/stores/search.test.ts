import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.hoisted(() => vi.fn());
const workspace = vi.hoisted(() => ({ currentWorkspaceId: 'ws-1' as string | null }));
vi.mock('./auth', () => ({ authFetch }));
vi.mock('@/lib/config', () => ({ getApiUrl: () => 'http://api' }));
vi.mock('@/stores/workspace', () => ({ useWorkspaceStore: { getState: () => workspace } }));

import { mapSettledWithConcurrency, SEARCH_ENGINE_CONCURRENCY, useSearchStore } from './search';

type Call = {
  engine: string;
  query: string;
  signal?: AbortSignal;
  resolve: (titles: { title: string; relevance?: number }[]) => void;
  reject: (error: Error) => void;
};

let calls: Call[] = [];
let inFlight = 0;
let maxInFlight = 0;

const engines = ['wikipedia', 'duckduckgo', 'google', 'brave'];

function enableEngines(ids: string[]) {
  useSearchStore.setState((state) => ({
    sources: state.sources.map((s) => ({ ...s, enabled: ids.includes(s.id) })),
  }));
}

const titles = () => useSearchStore.getState().results.map((r) => r.title);

beforeEach(() => {
  calls = [];
  inFlight = 0;
  maxInFlight = 0;
  workspace.currentWorkspaceId = 'ws-1';
  authFetch.mockReset();
  authFetch.mockImplementation(
    (_url: string, init: RequestInit) =>
      new Promise((resolve, reject) => {
        const body = JSON.parse(String(init.body)) as { query: string; engine?: string; source?: string };
        inFlight += 1;
        maxInFlight = Math.max(maxInFlight, inFlight);
        calls.push({
          engine: body.engine ?? body.source ?? '',
          query: body.query,
          signal: init.signal ?? undefined,
          resolve: (items) => {
            inFlight -= 1;
            resolve({
              ok: true,
              json: async () => ({
                results: items.map((item, i) => ({ id: `${body.engine}-${item.title}-${i}`, snippet: '', ...item })),
              }),
            });
          },
          reject: (error) => {
            inFlight -= 1;
            reject(error);
          },
        });
      }),
  );
  useSearchStore.setState({ allowedEngineIds: engines, query: '', results: [], loading: false, error: null });
  useSearchStore.getState().clearResults();
  enableEngines(['wikipedia', 'duckduckgo']);
});

describe('search stale responses', () => {
  it('a slow earlier query cannot overwrite the latest query', async () => {
    const first = useSearchStore.getState().search('old');
    const second = useSearchStore.getState().search('new');
    expect(calls.filter((c) => c.query === 'old').every((c) => c.signal?.aborted)).toBe(true);

    calls.filter((c) => c.query === 'new').forEach((c) => c.resolve([{ title: `new-${c.engine}` }]));
    await second;
    calls.filter((c) => c.query === 'old').forEach((c) => c.resolve([{ title: `old-${c.engine}` }]));
    await first;

    expect(titles().sort()).toEqual(['new-duckduckgo', 'new-wikipedia']);
    expect(useSearchStore.getState().query).toBe('new');
    expect(useSearchStore.getState().loading).toBe(false);
  });

  it('toggling an engine invalidates the search in flight', async () => {
    const pending = useSearchStore.getState().search('q');
    useSearchStore.getState().toggleSource('google');
    expect(useSearchStore.getState().loading).toBe(false);
    calls.forEach((c) => c.resolve([{ title: c.engine }]));
    await pending;
    expect(titles()).toEqual([]);
    expect(useSearchStore.getState().query).toBe('');
  });

  it('a workspace switch drops results computed for the previous workspace', async () => {
    useSearchStore.setState({ allowedEngineIds: ['conversations'] });
    enableEngines(['conversations']);
    const pending = useSearchStore.getState().search('q');
    workspace.currentWorkspaceId = 'ws-2';
    calls[0].resolve([{ title: 'ws-1 chat' }]);
    await pending;
    expect(titles()).toEqual([]);
    expect(useSearchStore.getState().loading).toBe(false);
  });

  it('clearing cancels the pending search without a user-facing error', async () => {
    const pending = useSearchStore.getState().search('q');
    useSearchStore.getState().clearResults();
    calls.forEach((c) => c.reject(new DOMException('aborted', 'AbortError') as unknown as Error));
    await pending;
    expect(useSearchStore.getState().error).toBeNull();
    expect(useSearchStore.getState().loading).toBe(false);
    expect(titles()).toEqual([]);
  });
});

describe('search partial failures', () => {
  it('keeps successful engines when one fails', async () => {
    const pending = useSearchStore.getState().search('q');
    calls.find((c) => c.engine === 'wikipedia')!.reject(new Error('Web search failed: 502'));
    calls.find((c) => c.engine === 'duckduckgo')!.resolve([{ title: 'ddg' }]);
    await pending;
    expect(titles()).toEqual(['ddg']);
    expect(useSearchStore.getState().error).toBeNull();
  });

  it('reports an error only when every engine fails', async () => {
    const pending = useSearchStore.getState().search('q');
    calls.forEach((c) => c.reject(new Error('Web search failed: 503')));
    await pending;
    expect(titles()).toEqual([]);
    expect(useSearchStore.getState().error).toBe('Web search failed: 503');
    expect(useSearchStore.getState().loading).toBe(false);
  });

  it('keeps source order and the relevance ranking', async () => {
    const pending = useSearchStore.getState().search('q');
    // Resolve out of order: duckduckgo first.
    calls.find((c) => c.engine === 'duckduckgo')!.resolve([{ title: 'd-low', relevance: 0.1 }, { title: 'd-tie', relevance: 0.5 }]);
    calls.find((c) => c.engine === 'wikipedia')!.resolve([{ title: 'w-tie', relevance: 0.5 }, { title: 'w-top', relevance: 0.9 }]);
    await pending;
    expect(titles()).toEqual(['w-top', 'w-tie', 'd-tie', 'd-low']);
  });
});

describe('search concurrency', () => {
  it('queries independent engines in parallel within the limit', async () => {
    enableEngines(engines);
    const pending = useSearchStore.getState().search('q');
    await Promise.resolve();
    expect(calls).toHaveLength(engines.length);
    expect(maxInFlight).toBe(Math.min(engines.length, SEARCH_ENGINE_CONCURRENCY));
    calls.forEach((c) => c.resolve([]));
    await pending;
  });

  it('never exceeds the concurrency limit', async () => {
    let active = 0;
    let peak = 0;
    const done = await mapSettledWithConcurrency([1, 2, 3, 4, 5, 6, 7], 3, async (n) => {
      active += 1;
      peak = Math.max(peak, active);
      await new Promise((r) => setTimeout(r, 5));
      active -= 1;
      if (n === 4) throw new Error('four');
      return n * 10;
    });
    expect(peak).toBe(3);
    expect(done.map((d) => (d.status === 'fulfilled' ? d.value : 'x'))).toEqual([10, 20, 30, 'x', 50, 60, 70]);
  });

  it('measures wall time with delayed engine fixtures (4 engines × 60ms)', async () => {
    const delay = 60;
    const items = engines;
    const sequentialStart = performance.now();
    for (const _ of items) await new Promise((r) => setTimeout(r, delay));
    const sequential = performance.now() - sequentialStart;

    const concurrentStart = performance.now();
    await mapSettledWithConcurrency(items, SEARCH_ENGINE_CONCURRENCY, () => new Promise((r) => setTimeout(r, delay)));
    const concurrent = performance.now() - concurrentStart;

    console.info(`search fixtures: sequential ${sequential.toFixed(0)}ms, concurrent ${concurrent.toFixed(0)}ms`);
    expect(sequential).toBeGreaterThanOrEqual(items.length * delay - 5);
    expect(concurrent).toBeLessThan(2 * delay);
  });
});
