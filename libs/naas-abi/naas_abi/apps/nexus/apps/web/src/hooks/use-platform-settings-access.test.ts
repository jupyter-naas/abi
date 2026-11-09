import { describe, expect, it, vi } from 'vitest';

vi.mock('@/stores/auth', () => ({ authFetch: vi.fn(), useAuthStore: vi.fn() }));

import { createPlatformSettingsAccessStore, fetchPlatformActions } from './use-platform-settings-access';

const answer = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const ADMIN = { 'nexus:ReadSystem': true, 'iam:ListPolicies': true };

describe('fetchPlatformActions', () => {
  it('reads the actions IAM grants, and nothing for a 401 or 403', async () => {
    expect(await fetchPlatformActions(async () => answer(200, { actions: ADMIN }))).toEqual(ADMIN);
    expect(await fetchPlatformActions(async () => answer(403))).toEqual({});
    expect(await fetchPlatformActions(async () => answer(401))).toEqual({});
    await expect(fetchPlatformActions(async () => answer(503))).rejects.toThrow('HTTP 503');
  });
});

describe('the access store', () => {
  it('asks once when two callers load for the same user at the same time', async () => {
    const fetcher = vi.fn(async () => answer(200, { actions: ADMIN }));
    const store = createPlatformSettingsAccessStore(fetcher);

    await Promise.all([store.getState().load('u1'), store.getState().load('u1')]);

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(store.getState()).toMatchObject({ status: 'ready', actions: ADMIN, pending: null });
  });

  it('asks again once the earlier call is over', async () => {
    const fetcher = vi.fn(async () => answer(200, { actions: ADMIN }));
    const store = createPlatformSettingsAccessStore(fetcher);

    await store.getState().load('u1');
    await store.getState().load('u1');

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('is an error when the first call fails, and a retry clears it', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(answer(503))
      .mockResolvedValueOnce(answer(200, { actions: ADMIN }));
    const store = createPlatformSettingsAccessStore(fetcher);

    await store.getState().load('u1');
    expect(store.getState()).toMatchObject({ status: 'error', actions: null });

    await store.getState().load('u1');
    expect(store.getState()).toMatchObject({ status: 'ready', actions: ADMIN });
  });

  it('keeps the last answer when a later call fails', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(answer(200, { actions: ADMIN }))
      .mockResolvedValueOnce(answer(503));
    const store = createPlatformSettingsAccessStore(fetcher);

    await store.getState().load('u1');
    await store.getState().load('u1');

    expect(store.getState()).toMatchObject({ status: 'ready', actions: ADMIN });
  });

  it('never reuses another user’s answer', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(answer(200, { actions: ADMIN }))
      .mockResolvedValueOnce(answer(503));
    const store = createPlatformSettingsAccessStore(fetcher);

    await store.getState().load('u1');
    await store.getState().load('u2');

    expect(store.getState()).toMatchObject({ userId: 'u2', status: 'error', actions: null });
  });
});
