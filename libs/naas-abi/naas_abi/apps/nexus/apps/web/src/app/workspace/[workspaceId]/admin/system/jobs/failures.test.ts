// @vitest-environment jsdom
import { createElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Result } from '../data/data-api';
import { mount, type Mounted } from '../system-render';
import type { JobsApi } from './jobs-api';
import { run } from './jobs-fixtures';
import type { JobFailures } from './jobs-types';
import { SEEN_KEY, useJobFailures } from './failures';

let mounted: Mounted | null = null;
let seen: ReturnType<typeof useJobFailures> | null = null;

function Probe({ api }: { api: JobsApi }) {
  seen = useJobFailures(api, true);
  return createElement('span', null, String(seen.failures?.count ?? '-'));
}

const failures = (count: number): JobFailures => ({
  since: '2026-10-01T09:00:00+00:00',
  count,
  more: false,
  runs: Array.from({ length: count }, (_, i) => run({ key: `m/j:${i}`, status: 'FAILED' })),
});

beforeEach(() => window.localStorage.clear());
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  seen = null;
});

describe('job failure notifications', () => {
  it('reads failures since the last time they were seen, then since now once marked', async () => {
    const calls: (string | null | undefined)[] = [];
    const api = {
      failures: vi.fn((since?: string | null): Promise<Result<JobFailures>> => {
        calls.push(since);
        return Promise.resolve({ ok: true, data: failures(calls.length === 1 ? 2 : 0) });
      }),
    } as unknown as JobsApi;

    mounted = await mount(Probe, { api });
    await mounted.flush();
    expect(calls[0]).toBeNull();
    expect(mounted.host.textContent).toBe('2');

    const before = Date.now();
    await import('react').then(({ act }) => act(async () => seen?.markSeen()));
    await mounted.flush();

    const stored = window.localStorage.getItem(SEEN_KEY);
    expect(stored && Date.parse(stored) >= before - 1000).toBe(true);
    expect(calls.at(-1)).toBe(stored);
    expect(mounted.host.textContent).toBe('0');
  });

  it('keeps working when storage is unavailable', async () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    const api = { failures: vi.fn(() => Promise.resolve({ ok: true as const, data: failures(1) })) } as unknown as JobsApi;

    mounted = await mount(Probe, { api });
    await mounted.flush();

    expect(mounted.host.textContent).toBe('1');
    getItem.mockRestore();
  });
});
