// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { mount } from './system-render';
import { usePoll, type Poll } from './use-poll';

function Probe({ fn, ms, enabled = true, dep = 0 }: { fn: Poll; ms: number; enabled?: boolean; dep?: number }) {
  usePoll(fn, ms, enabled, [dep]);
  return null;
}

/** A poll whose calls answer when the test says so. */
function deferredPoll() {
  const calls: { signal: AbortSignal; resolve: () => void; reject: (e: unknown) => void }[] = [];
  const fn = vi.fn((signal: AbortSignal) => {
    return new Promise<void>((resolve, reject) => {
      calls.push({ signal, resolve, reject });
    });
  });
  return { fn, calls };
}

const advance = (ms: number) => act(async () => void (await vi.advanceTimersByTimeAsync(ms)));
const settle = (run: () => void) => act(async () => run());

describe('usePoll', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('never sends a call while the previous one is pending', async () => {
    const { fn, calls } = deferredPoll();
    const mounted = await mount(Probe, { fn, ms: 1000 });
    expect(fn).toHaveBeenCalledTimes(1);

    await advance(10_000);
    expect(fn).toHaveBeenCalledTimes(1);

    await settle(() => calls[0].resolve());
    await advance(999);
    expect(fn).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fn).toHaveBeenCalledTimes(2);
    await mounted.unmount();
  });

  it('skips ticks while the page is hidden', async () => {
    const fn = vi.fn(() => Promise.resolve());
    const mounted = await mount(Probe, { fn, ms: 1000 });
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    await advance(5000);
    expect(fn).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    await advance(1000);
    expect(fn).toHaveBeenCalledTimes(2);
    await mounted.unmount();
  });

  it('keeps polling after a failed call', async () => {
    const { fn, calls } = deferredPoll();
    const mounted = await mount(Probe, { fn, ms: 1000 });
    await settle(() => calls[0].reject(new Error('503')));
    await advance(1000);
    expect(fn).toHaveBeenCalledTimes(2);
    await mounted.unmount();
  });

  it('aborts the pending call and stops on unmount', async () => {
    const { fn, calls } = deferredPoll();
    const mounted = await mount(Probe, { fn, ms: 1000 });
    await mounted.unmount();
    expect(calls[0].signal.aborted).toBe(true);

    calls[0].resolve();
    await advance(10_000);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('aborts and starts over when its dependencies change', async () => {
    const { fn, calls } = deferredPoll();
    const host = document.createElement('div');
    const root = createRoot(host);
    const render = (dep: number) => act(async () => root.render(createElement(Probe, { fn, ms: 1000, dep })));
    await render(1);
    expect(fn).toHaveBeenCalledTimes(1);

    await render(2);
    expect(calls[0].signal.aborted).toBe(true);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(calls[1].signal.aborted).toBe(false);

    // The aborted call answering late does not schedule a second poll loop.
    await settle(() => calls[0].resolve());
    await settle(() => calls[1].resolve());
    await advance(1000);
    expect(fn).toHaveBeenCalledTimes(3);
    await act(async () => root.unmount());
  });

  it('does nothing while disabled', async () => {
    const fn = vi.fn(() => Promise.resolve());
    const mounted = await mount(Probe, { fn, ms: 1000, enabled: false });
    await advance(5000);
    expect(fn).not.toHaveBeenCalled();
    await mounted.unmount();
  });
});
