// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { useWorkspaceStore } from '@/stores/workspace';
import { FIRST_RETRY_MS, useWorkspacesReady } from './use-workspaces-ready';

let mounted: Mounted | null = null;
let seen: { ready: boolean; retrying: boolean } | null = null;

function Probe() {
  seen = useWorkspacesReady(true);
  return createElement('span', null, seen.ready ? 'ready' : seen.retrying ? 'retrying' : 'loading');
}

beforeEach(() => {
  vi.useFakeTimers();
  useWorkspaceStore.setState({ workspacesReady: false });
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  vi.useRealTimers();
});

describe('useWorkspacesReady', () => {
  it('asks again while the API does not answer, and stops once it does', async () => {
    let answers = false;
    const fetchWorkspaces = vi.fn(async () => {
      if (answers) useWorkspaceStore.setState({ workspacesReady: true });
    });
    useWorkspaceStore.setState({ fetchWorkspaces });
    mounted = await mount(Probe, {});
    await act(async () => undefined);
    expect(fetchWorkspaces).toHaveBeenCalledTimes(1);
    expect(seen).toEqual({ ready: false, retrying: true });

    await act(async () => vi.advanceTimersByTimeAsync(FIRST_RETRY_MS));
    expect(fetchWorkspaces).toHaveBeenCalledTimes(2); // retried after 1 s

    answers = true;
    await act(async () => vi.advanceTimersByTimeAsync(2 * FIRST_RETRY_MS)); // then after 2 s
    expect(fetchWorkspaces).toHaveBeenCalledTimes(3);
    expect(seen?.ready).toBe(true);

    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(fetchWorkspaces).toHaveBeenCalledTimes(3); // answered: asked no more
  });
});
