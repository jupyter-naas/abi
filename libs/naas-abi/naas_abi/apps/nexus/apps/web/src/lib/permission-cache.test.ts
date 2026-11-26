import { describe, expect, it, vi } from 'vitest';
import {
  changesPermissions, createPermissionCache, permissionReadKey,
  PermissionSessionChanged, PERMISSION_TTL_MS, PERMISSION_DENIED_TTL_MS,
} from './permission-cache';

const json = (body: unknown, status = 200) => Response.json(body, { status });
function cache(limit?: number) {
  let time = 100;
  const store = createPermissionCache(() => time, limit);
  store.getState().identify('api-a:user-a:session-a');
  return { store, advance: (ms: number) => { time += ms; } };
}

describe('permission memory cache', () => {
  it('shares the wire request and gives each concurrent consumer a readable body', async () => {
    const { store } = cache();
    const load = vi.fn(async () => json({ actions: { read: true } }));
    const answers = await Promise.all(Array.from({ length: 5 }, () => store.getState().read('workspace-a', load)));
    expect(load).toHaveBeenCalledTimes(1);
    expect(await Promise.all(answers.map((answer) => answer.json()))).toEqual(
      Array.from({ length: 5 }, () => ({ actions: { read: true } })),
    );
    await store.getState().read('workspace-a', load);
    expect(load).toHaveBeenCalledTimes(1);
    expect(store.getState().entries.get('workspace-a')?.status).toBe('ready');
  });

  it('expires permissions and replaces previous grants with a refusal', async () => {
    const { store, advance } = cache();
    const load = vi.fn().mockResolvedValueOnce(json({ actions: { write: true } })).mockResolvedValue(json({}, 403));
    await store.getState().read('org-a', load);
    advance(PERMISSION_TTL_MS);
    const refused = await store.getState().read('org-a', load);
    expect(refused.status).toBe(403);
    expect(store.getState().entries.get('org-a')?.status).toBe('denied');
    await store.getState().read('org-a', load);
    expect(load).toHaveBeenCalledTimes(2);
    advance(PERMISSION_DENIED_TTL_MS);
    await store.getState().read('org-a', load);
    expect(load).toHaveBeenCalledTimes(3);
  });

  it('force refreshes settled answers, but concurrent refreshes still share one request', async () => {
    const { store } = cache();
    const load = vi.fn(async () => json({ actions: {} }));
    await store.getState().read('platform', load);
    await Promise.all([store.getState().read('platform', load, { force: true }), store.getState().read('platform', load, { force: true })]);
    expect(load).toHaveBeenCalledTimes(2);
  });

  it('propagates an observed revocation to other scopes and rejects their older flights', async () => {
    const { store } = cache();
    await store.getState().read('platform', async () => json({ actions: { admin: true } }));
    await store.getState().read('workspace', async () => json({ actions: { write: true } }));
    let finish!: (response: Response) => void;
    const older = store.getState().read('organization', () => new Promise<Response>((resolve) => { finish = resolve; }));
    const rejected = expect(older).rejects.toBeInstanceOf(PermissionSessionChanged);
    await Promise.resolve();
    const refreshed = await store.getState().read('platform', async () => json({ actions: {} }), { force: true });
    expect(await refreshed.json()).toEqual({ actions: {} });
    expect([...store.getState().entries.keys()]).toEqual(['platform']);
    finish(json({ actions: { admin: true } }));
    await rejected;
    const fetchWorkspace = vi.fn(async () => json({ actions: {} }));
    await store.getState().read('workspace', fetchWorkspace);
    expect(fetchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('does not mistake a transient error for a principal-wide permission change', async () => {
    const { store } = cache();
    await store.getState().read('platform', async () => json({ actions: { read: true } }));
    await store.getState().read('workspace', async () => json({ actions: { read: true } }));
    const generation = store.getState().generation;
    await store.getState().read('platform', async () => json({ detail: 'unavailable' }, 503), { force: true });
    expect(store.getState().generation).toBe(generation);
    const fetchWorkspace = vi.fn(async () => json({ actions: {} }));
    expect((await (await store.getState().read('workspace', fetchWorkspace)).json()).actions.read).toBe(true);
    expect(fetchWorkspace).not.toHaveBeenCalled();
  });

  it('rejects older responses after an A-B-A identity switch', async () => {
    const { store } = cache();
    let finish!: (response: Response) => void;
    const older = store.getState().read('platform', () => new Promise<Response>((resolve) => { finish = resolve; }));
    const rejected = expect(older).rejects.toBeInstanceOf(PermissionSessionChanged);
    await Promise.resolve();
    store.getState().identify('other');
    store.getState().identify('api-a:user-a:session-a');
    await store.getState().read('platform', async () => json({ actions: {} }));
    finish(json({ actions: { admin: true } }));
    await rejected;
    expect(await (await store.getState().read('platform', async () => json('wrong'))).json()).toEqual({ actions: {} });
  });

  it('discards a response invalidated by a mutation even when the identity did not change', async () => {
    const { store } = cache();
    let finish!: (response: Response) => void;
    const old = store.getState().read('platform', () => new Promise<Response>((resolve) => { finish = resolve; }));
    const rejected = expect(old).rejects.toBeInstanceOf(PermissionSessionChanged);
    await Promise.resolve();
    store.getState().invalidate();
    finish(json({ actions: { admin: true } }));
    await rejected;
    expect(store.getState().entries.size).toBe(0);
  });

  it('does not deliver a cached grant to a caller overtaken by logout', async () => {
    const { store } = cache();
    await store.getState().read('platform', async () => json({ actions: { admin: true } }));
    const reading = store.getState().read('platform', async () => json({}));
    store.getState().invalidate();
    await expect(reading).rejects.toBeInstanceOf(PermissionSessionChanged);
  });

  it('bounds memory, keeps in-flight reads deduplicated, and guards overflow responses too', async () => {
    const { store } = cache(1);
    let finish!: (response: Response) => void;
    const first = store.getState().read('a', () => new Promise<Response>((resolve) => { finish = resolve; }));
    const rejected = expect(first).rejects.toBeInstanceOf(PermissionSessionChanged);
    await Promise.resolve();
    let overflow!: (response: Response) => void;
    const second = store.getState().read('b', () => new Promise<Response>((resolve) => { overflow = resolve; }));
    const rejectedOverflow = expect(second).rejects.toBeInstanceOf(PermissionSessionChanged);
    await Promise.resolve();
    expect(store.getState().entries.size).toBe(1);
    store.getState().invalidate();
    finish(json('old'));
    overflow(json('old'));
    await Promise.all([rejected, rejectedOverflow]);
    await store.getState().read('a', async () => json('a'));
    await store.getState().read('b', async () => json('b'));
    expect([...store.getState().entries.keys()]).toEqual(['b']);
  });

  it('retries transient failures after a short backoff rather than granting access', async () => {
    const { store, advance } = cache();
    const load = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(json({ actions: {} }));
    await expect(store.getState().read('a', load)).rejects.toThrow('offline');
    await expect(store.getState().read('a', load)).rejects.toThrow('offline');
    expect(load).toHaveBeenCalledTimes(1);
    expect(store.getState().entries.get('a')?.status).toBe('error');
    advance(2001);
    await store.getState().read('a', load);
    expect(load).toHaveBeenCalledTimes(2);
  });

  it('does not cache an unknown session or oversized permission payload', async () => {
    const store = createPermissionCache();
    const load = vi.fn(async () => json({ actions: {} }));
    await store.getState().read('a', load);
    await store.getState().read('a', load);
    expect(load).toHaveBeenCalledTimes(2);
    expect(store.getState().entries.size).toBe(0);
    store.getState().identify('ready');
    await store.getState().read('a', async () => json('x'.repeat(256 * 1024)));
    expect(store.getState().entries.size).toBe(0);
  });

  it('revalidates on focus only when a read is stale', async () => {
    const { store, advance } = cache();
    await store.getState().read('a', async () => json({ actions: {} }));
    store.getState().revalidate();
    expect(store.getState().revision).toBe(0);
    advance(PERMISSION_TTL_MS);
    store.getState().revalidate();
    expect(store.getState().revision).toBe(1);
  });
});

describe('permission request boundaries', () => {
  const base = 'https://api.example.test';
  it('canonicalizes the platform but isolates scopes and leaves other data live', () => {
    expect(permissionReadKey(`${base}/api/iam/admin/access`, base)).toBe(permissionReadKey(`${base}/api/iam/admin/access?scope=abi%3A`, base));
    expect(permissionReadKey(`${base}/api/iam/admin/access?scope=one`, base)).not.toBe(permissionReadKey(`${base}/api/iam/admin/access?scope=two`, base));
    for (const url of ['/api/agents', '/api/secrets/ws', '/api/auth/me', '/api/iam/admin/policies', '/api/organizations']) {
      expect(permissionReadKey(`${base}${url}`, base)).toBeNull();
    }
    expect(permissionReadKey(`${base}/api/organizations`, base, { cache: 'force-cache' })).not.toBeNull();
  });
  it('bypasses credential overrides, abort signals, foreign APIs and ambiguous scopes', () => {
    const url = `${base}/api/iam/admin/access`;
    expect(permissionReadKey(url, base, { headers: { Authorization: 'Bearer restricted' } })).toBeNull();
    expect(permissionReadKey(url, base, { signal: new AbortController().signal })).toBeNull();
    expect(permissionReadKey(url, base, { cache: 'no-store' })).toBeNull();
    expect(permissionReadKey(url, 'https://other.test')).toBeNull();
    expect(permissionReadKey(`${url}?scope=a&scope=b`, base)).toBeNull();
  });
  it('invalidates IAM and membership changes, not simulations, sync or unrelated saves', () => {
    for (const path of ['/api/iam/admin/groups/g/members/u', '/api/iam/admin/policies/p', '/api/workspaces/w/members/u', '/api/settings-cache/refresh']) {
      expect(changesPermissions(`${base}${path}`, 'POST', base)).toBe(true);
    }
    for (const path of ['/api/iam/admin/simulate', '/api/iam/admin/policies/validate', '/api/agents/sync', '/api/agents/a', '/api/chat/messages']) {
      expect(changesPermissions(`${base}${path}`, 'POST', base)).toBe(false);
    }
  });
});
