import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createDeferredStorage, discardDeferredStorage, flushDeferredStorage } from './deferred-storage';

function memoryBackend() {
  const data = new Map<string, string>();
  const backend = {
    getItem: vi.fn((k: string) => data.get(k) ?? null),
    setItem: vi.fn((k: string, v: string) => { data.set(k, v); }),
    removeItem: vi.fn((k: string) => { data.delete(k); }),
  };
  return { data, backend };
}

describe('createDeferredStorage', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    discardDeferredStorage();
    vi.useRealTimers();
  });

  it('does not serialize or write inside the set call', () => {
    const { backend } = memoryBackend();
    const storage = createDeferredStorage<{ n: number }>(() => backend);
    storage.setItem('k', { state: { n: 1 } });
    expect(backend.setItem).not.toHaveBeenCalled();
  });

  it('coalesces bursts of sets into one write of the latest state', () => {
    const { data, backend } = memoryBackend();
    const storage = createDeferredStorage<{ n: number }>(() => backend);
    for (let n = 1; n <= 50; n++) storage.setItem('k', { state: { n } });
    vi.advanceTimersByTime(1000);
    expect(backend.setItem).toHaveBeenCalledTimes(1);
    expect(JSON.parse(data.get('k')!)).toEqual({ state: { n: 50 } });
  });

  it('reads back a queued value before it is flushed', () => {
    const { backend } = memoryBackend();
    const storage = createDeferredStorage<{ n: number }>(() => backend);
    storage.setItem('k', { state: { n: 7 }, version: 2 });
    expect(storage.getItem('k')).toEqual({ state: { n: 7 }, version: 2 });
  });

  it('flushes on demand (page hide)', () => {
    const { data, backend } = memoryBackend();
    const storage = createDeferredStorage<{ n: number }>(() => backend);
    storage.setItem('k', { state: { n: 3 } });
    flushDeferredStorage();
    expect(JSON.parse(data.get('k')!)).toEqual({ state: { n: 3 } });
  });

  it('never resurrects a key cleared on logout', () => {
    // The regression: a queued write landing after logout's removeItem would
    // restore the previous user's persisted state.
    const { data, backend } = memoryBackend();
    const storage = createDeferredStorage<{ n: number }>(() => backend);
    storage.setItem('nexus-agents', { state: { n: 1 } });
    discardDeferredStorage(['nexus-agents']);
    backend.removeItem('nexus-agents');
    flushDeferredStorage();
    vi.advanceTimersByTime(5000);
    expect(data.has('nexus-agents')).toBe(false);
  });
});
