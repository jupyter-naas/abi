import { beforeEach, describe, expect, it, vi } from 'vitest';

type AuthSnapshot = { user: { id: string } | null; token: string | null };
type AuthListener = (state: AuthSnapshot, previous: AuthSnapshot) => void;

const authFetch = vi.fn();
// The module subscribes to window events at import time.
vi.hoisted(() => {
  (globalThis as { window?: EventTarget }).window = new EventTarget();
});
const auth = vi.hoisted(() => ({
  state: { user: { id: 'u1' }, token: 't1' } as AuthSnapshot,
  listeners: [] as AuthListener[],
}));

vi.mock('@/stores/auth', () => ({
  authFetch: (...args: unknown[]) => authFetch(...args),
  useAuthStore: {
    getState: () => auth.state,
    subscribe: (listener: AuthListener) => auth.listeners.push(listener),
  },
}));

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'http://api' }));

import {
  clearOrgBrandingCache,
  invalidateOrgBranding,
  loadOrgBranding,
  parseOrgShellBranding,
  resolveWorkspaceOrgId,
} from './org-branding';

const ok = (body: unknown) => ({ ok: true, json: async () => body });

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

function setAuth(next: AuthSnapshot) {
  const previous = auth.state;
  auth.state = next;
  for (const listener of auth.listeners) listener(next, previous);
}

describe('parseOrgShellBranding', () => {
  it('keeps a zero radius and only accepts known themes', () => {
    expect(parseOrgShellBranding({ login_border_radius: '0', default_theme: 'dark' })).toEqual({
      borderRadius: '0',
      defaultTheme: 'dark',
    });
    expect(parseOrgShellBranding({ default_theme: 'neon' })).toEqual({
      borderRadius: '0',
      defaultTheme: undefined,
    });
  });
});

describe('loadOrgBranding', () => {
  beforeEach(() => {
    authFetch.mockReset();
    auth.state = { user: { id: 'u1' }, token: 't1' };
    clearOrgBrandingCache();
  });

  it('reuses one request for every workspace of an organization', async () => {
    const reply = deferred<unknown>();
    authFetch.mockReturnValueOnce(reply.promise);

    const first = loadOrgBranding('org-a');
    const second = loadOrgBranding('org-a');
    reply.resolve(ok({ login_border_radius: '12' }));

    expect(await first).toEqual({ borderRadius: '12', defaultTheme: undefined });
    expect(await second).toBe(await first);
    expect(await loadOrgBranding('org-a')).toBe(await first);
    expect(authFetch).toHaveBeenCalledTimes(1);
    expect(authFetch).toHaveBeenCalledWith('/api/organizations/org-a');
  });

  it('does not cache failures', async () => {
    authFetch.mockResolvedValueOnce({ ok: false, status: 500 });
    authFetch.mockRejectedValueOnce(new Error('offline'));
    authFetch.mockResolvedValueOnce(ok({ login_border_radius: '4' }));

    expect(await loadOrgBranding('org-a')).toBeNull();
    expect(await loadOrgBranding('org-a')).toBeNull();
    expect(await loadOrgBranding('org-a')).toEqual({ borderRadius: '4', defaultTheme: undefined });
    expect(authFetch).toHaveBeenCalledTimes(3);
  });

  it('refetches an organization after its branding is edited', async () => {
    authFetch.mockResolvedValueOnce(ok({ login_border_radius: '4' }));
    authFetch.mockResolvedValueOnce(ok({ login_border_radius: '8' }));
    authFetch.mockResolvedValueOnce(ok({ login_border_radius: '2' }));

    await loadOrgBranding('org-a');
    await loadOrgBranding('org-b');
    invalidateOrgBranding('org-a');

    expect((await loadOrgBranding('org-a'))?.borderRadius).toBe('2');
    expect((await loadOrgBranding('org-b'))?.borderRadius).toBe('8');
    expect(authFetch).toHaveBeenCalledTimes(3);
  });

  it('clears on the org-branding-updated event', async () => {
    authFetch.mockResolvedValue(ok({ login_border_radius: '4' }));
    await loadOrgBranding('org-a');
    window.dispatchEvent(new Event('org-branding-updated'));
    await loadOrgBranding('org-a');
    expect(authFetch).toHaveBeenCalledTimes(2);
  });

  it('does not let a request from before logout fill the next session cache', async () => {
    const stale = deferred<unknown>();
    authFetch.mockReturnValueOnce(stale.promise);
    authFetch.mockResolvedValue(ok({ login_border_radius: '9' }));

    const before = loadOrgBranding('org-a');
    setAuth({ user: null, token: null });
    setAuth({ user: { id: 'u2' }, token: 't2' });
    stale.resolve(ok({ login_border_radius: '1' }));
    await before;

    expect((await loadOrgBranding('org-a'))?.borderRadius).toBe('9');
    expect(authFetch).toHaveBeenCalledTimes(2);
  });
});

describe('resolveWorkspaceOrgId', () => {
  beforeEach(() => authFetch.mockReset());

  it('uses the loaded workspace record without a lookup', async () => {
    expect(await resolveWorkspaceOrgId('ws-1', 'org-a')).toBe('org-a');
    expect(authFetch).not.toHaveBeenCalled();
  });

  it('falls back to workspace details when the record lacks the org', async () => {
    authFetch.mockResolvedValueOnce(ok({ organization_id: 'org-b' }));
    expect(await resolveWorkspaceOrgId('ws-1')).toBe('org-b');
    expect(authFetch).toHaveBeenCalledWith('/api/workspaces/ws-1');

    authFetch.mockResolvedValueOnce({ ok: false, status: 404 });
    expect(await resolveWorkspaceOrgId('ws-2')).toBeNull();
  });
});
