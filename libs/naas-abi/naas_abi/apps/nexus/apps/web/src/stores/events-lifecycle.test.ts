// @vitest-environment jsdom
/**
 * The Events live tail (#1609): one read at a time, none while paused, hidden or unwatched,
 * an answer for earlier filters never lands, and what it remembers stays bounded however
 * many events arrive.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlatformEvent } from '@/app/settings/system/events/bfo-event-projection';

const mocks = vi.hoisted(() => ({
  authFetch: null as unknown as ReturnType<typeof import('vitest').vi.fn>,
}));

vi.mock('@/stores/auth', () => ({ authFetch: (...args: unknown[]) => mocks.authFetch(...args) }));
vi.mock('@/hooks/use-platform-settings-access', () => ({
  fetchPlatformActions: async () => ({ 'nexus:ReadSystem': true }),
}));
vi.mock('@/lib/permission-cache', async () => {
  const { create } = await import('zustand');
  const usePermissionCache = create(() => ({ enabled: true, generation: 0, revision: 0, identity: 'one' }));
  return { usePermissionCache, permissionSessionKey: () => 'one' };
});

type EventsModule = typeof import('./events');

let seq = 0;
function event(): PlatformEvent {
  seq += 1;
  return { _uri: `urn:event:${seq}`, _seq: seq, created_at: new Date(seq * 1000).toISOString() } as unknown as PlatformEvent;
}

/** Newest last, as the API answers. */
function batch(count: number): PlatformEvent[] {
  return Array.from({ length: count }, () => event());
}

type Pending = { url: string; signal?: AbortSignal | null; resolve: (body: unknown) => void };

function pendingFetch() {
  const calls: Pending[] = [];
  mocks.authFetch = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith('/events/types')) return Promise.resolve(Response.json([]));
    return new Promise<Response>((resolve) => {
      calls.push({ url, signal: init?.signal, resolve: (body) => resolve(Response.json(body)) });
    });
  });
  return calls;
}

const recentReads = () =>
  (mocks.authFetch.mock.calls as [string][]).filter(([url]) => url.includes('/events/recent')).length;

async function flush() {
  for (let i = 0; i < 5; i += 1) await vi.advanceTimersByTimeAsync(0);
}

let events: EventsModule;
let unsubscribe: (() => void) | null = null;

beforeEach(async () => {
  vi.useFakeTimers();
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  vi.resetModules();
  events = await import('./events');
});

afterEach(() => {
  unsubscribe?.();
  unsubscribe = null;
  vi.useRealTimers();
});

describe('the Events live tail', () => {
  it('never sends a read while the previous one is pending', async () => {
    const calls = pendingFetch();
    unsubscribe = events.useEventsStore.getState().subscribe();
    await flush();
    expect(recentReads()).toBe(1);

    await vi.advanceTimersByTimeAsync(60_000);
    expect(recentReads()).toBe(1);

    calls[0].resolve(batch(3));
    await flush();
    expect(events.useEventsStore.getState().events).toHaveLength(3);
    await vi.advanceTimersByTimeAsync(events.EVENTS_POLL_INTERVAL_MS);
    expect(recentReads()).toBe(2);
  });

  it('reads nothing while paused or hidden, and again once resumed', async () => {
    const calls = pendingFetch();
    unsubscribe = events.useEventsStore.getState().subscribe();
    await flush();
    calls[0].resolve([]);
    await flush();

    events.useEventsStore.getState().setPaused(true);
    await vi.advanceTimersByTimeAsync(events.EVENTS_POLL_INTERVAL_MS * 5);
    expect(recentReads()).toBe(1);

    events.useEventsStore.getState().setPaused(false);
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    await vi.advanceTimersByTimeAsync(events.EVENTS_POLL_INTERVAL_MS * 5);
    expect(recentReads()).toBe(1);

    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    await vi.advanceTimersByTimeAsync(events.EVENTS_POLL_INTERVAL_MS);
    expect(recentReads()).toBe(2);
  });

  it('stops reading when the last viewer leaves and keeps the feed for its return', async () => {
    const calls = pendingFetch();
    unsubscribe = events.useEventsStore.getState().subscribe();
    await flush();
    calls[0].resolve(batch(2));
    await flush();
    unsubscribe();
    unsubscribe = null;

    await vi.advanceTimersByTimeAsync(events.EVENTS_POLL_INTERVAL_MS * 10);
    expect(recentReads()).toBe(1);
    expect(events.useEventsStore.getState().events).toHaveLength(2);
  });

  it('aborts and drops an answer begun under the previous filters', async () => {
    const calls = pendingFetch();
    unsubscribe = events.useEventsStore.getState().subscribe();
    await flush();
    events.useEventsStore.getState().setSearch('deploy');
    await flush();
    expect(calls[0].signal?.aborted).toBe(true);
    expect(calls[1].url).toContain('q=deploy');

    calls[0].resolve(batch(4));
    calls[1].resolve(batch(1));
    await flush();
    expect(events.useEventsStore.getState().events).toHaveLength(1);
  });

  it('remembers no more events than it holds, however many arrive', async () => {
    const calls = pendingFetch();
    unsubscribe = events.useEventsStore.getState().subscribe();
    await flush();
    for (let i = 0; i < 30; i += 1) {
      calls[i].resolve(batch(events.EVENTS_PAGE_SIZE));
      await flush();
      await vi.advanceTimersByTimeAsync(events.EVENTS_POLL_INTERVAL_MS);
    }
    const held = events.useEventsStore.getState().events.length;
    expect(held).toBe(events.MAX_EVENTS);
    expect(events.seenEventCount()).toBe(held);

    // A row already held does not come back as new.
    const newest = events.useEventsStore.getState().events[0].event;
    calls[30].resolve([newest]);
    await flush();
    expect(events.useEventsStore.getState().events.length).toBe(held);
  });

  it('forgets what it remembered when cleared', async () => {
    const calls = pendingFetch();
    unsubscribe = events.useEventsStore.getState().subscribe();
    await flush();
    calls[0].resolve(batch(5));
    await flush();
    events.useEventsStore.getState().clear();
    expect(events.seenEventCount()).toBe(0);
  });
});
