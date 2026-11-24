// @vitest-environment jsdom
/**
 * A System view's read (#1609): one call at a time, nothing while the view is closed,
 * and an answer begun for an earlier view (another nonce or path) never shows.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import type { Loaded } from './system-api';
import { useSystemResource, type SystemLoader } from './system-resource';

type Call = { path: string; signal: AbortSignal; resolve: (value: Loaded<string>) => void };

function deferredLoader() {
  const calls: Call[] = [];
  const load = vi.fn(
    (path: string, signal: AbortSignal) =>
      new Promise<Loaded<string>>((resolve) => {
        calls.push({ path, signal, resolve });
      }),
  ) as unknown as SystemLoader & ReturnType<typeof vi.fn>;
  return { load, calls };
}

let root: Root | null = null;
let host: HTMLDivElement | null = null;

function Probe(props: { path: string; enabled: boolean; nonce: number; load: SystemLoader }) {
  const state = useSystemResource<string>(props.path, {
    enabled: props.enabled,
    intervalMs: 1000,
    nonce: props.nonce,
    load: props.load,
  });
  return createElement('p', null, state === null ? 'loading' : state.ok ? state.data : `failed ${state.reason}`);
}

async function render(props: { path?: string; enabled?: boolean; nonce?: number; load: SystemLoader }) {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  if (!host) {
    host = document.createElement('div');
    document.body.append(host);
    root = createRoot(host);
  }
  const full = { path: '/overview', enabled: true, nonce: 0, ...props };
  await act(async () => root!.render(createElement(Probe, full)));
}

const text = () => host?.textContent;
const advance = (ms: number) => act(async () => void (await vi.advanceTimersByTimeAsync(ms)));
const answer = (call: Call, data: string) => act(async () => call.resolve({ ok: true, data }));

describe('useSystemResource', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  });
  afterEach(async () => {
    await act(async () => root?.unmount());
    host?.remove();
    root = null;
    host = null;
    vi.useRealTimers();
  });

  it('never sends a second read while the first is pending', async () => {
    const { load, calls } = deferredLoader();
    await render({ load });
    expect(load).toHaveBeenCalledTimes(1);

    // A slow server: the interval elapses many times without a new call.
    await advance(30_000);
    expect(load).toHaveBeenCalledTimes(1);

    await answer(calls[0], 'first');
    expect(text()).toBe('first');
    await advance(1000);
    expect(load).toHaveBeenCalledTimes(2);
  });

  it('stops reading when the view closes and aborts the pending read', async () => {
    const { load, calls } = deferredLoader();
    await render({ load });
    await render({ load, enabled: false });
    expect(calls[0].signal.aborted).toBe(true);

    await advance(30_000);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('ignores an answer begun before Refresh', async () => {
    const { load, calls } = deferredLoader();
    await render({ load, nonce: 0 });
    await render({ load, nonce: 1 });
    expect(calls[0].signal.aborted).toBe(true);
    expect(load).toHaveBeenCalledTimes(2);

    await answer(calls[1], 'fresh');
    await answer(calls[0], 'stale');
    expect(text()).toBe('fresh');
  });

  it('shows nothing of another path while its own read is pending', async () => {
    const { load, calls } = deferredLoader();
    await render({ load, path: '/nats/server' });
    await answer(calls[0], 'server');
    expect(text()).toBe('server');

    // The answer kept for the earlier path is not shown for the new one.
    await render({ load, path: '/nats/connections' });
    expect(text()).toBe('loading');
    await answer(calls[1], 'connections');
    expect(text()).toBe('connections');
  });

  it('drops a late answer for the path left', async () => {
    const { load, calls } = deferredLoader();
    await render({ load, path: '/nats/server' });
    await render({ load, path: '/nats/connections' });
    await answer(calls[0], 'late server');
    expect(text()).toBe('loading');
    await answer(calls[1], 'connections');
    expect(text()).toBe('connections');
  });

  it('skips reads while the page is hidden', async () => {
    const { load, calls } = deferredLoader();
    await render({ load });
    await answer(calls[0], 'first');
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    await advance(10_000);
    expect(load).toHaveBeenCalledTimes(1);
  });
});
