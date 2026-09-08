import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { authFetch, syncPersistedAuthSession, useAuthStore } from './auth';
import { getSafeStorage } from '@/lib/safe-storage';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));
const jwt = () => `header.${btoa(JSON.stringify({ exp: Date.now() / 1000 + 1800 }))}.signature`;
const response = (status: number, body = {}) => new Response(JSON.stringify(body), { status });
const session = () => useAuthStore.setState({
  token: jwt(), refreshToken: 'refresh-old', isAuthenticated: true,
  user: { id: '1', email: 'test@example.test', name: 'Test', createdAt: new Date() },
});

beforeEach(() => {
  session();
  vi.stubGlobal('fetch', vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

describe('session renewal', () => {
  it('shares one rotation across concurrent callers', async () => {
    vi.mocked(fetch).mockResolvedValue(response(200, { access_token: jwt(), refresh_token: 'refresh-new' }));
    expect(await Promise.all(Array.from({ length: 5 }, () => useAuthStore.getState().refreshAccessToken())))
      .toEqual([true, true, true, true, true]);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().refreshToken).toBe('refresh-new');
  });

  it.each([429, 500, 502, 503])('keeps credentials after refresh HTTP %s', async (status) => {
    vi.mocked(fetch).mockResolvedValue(response(status));
    expect(await useAuthStore.getState().refreshAccessToken()).toBe(false);
    expect(useAuthStore.getState().refreshToken).toBe('refresh-old');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('keeps the session when /me expires and refresh is offline', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(401)).mockRejectedValueOnce(new TypeError('offline'));
    expect(await useAuthStore.getState().checkAuth()).toBe(true);
    expect(useAuthStore.getState().refreshToken).toBe('refresh-old');
  });

  it('keeps the session when the /me retry has a server error', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access_token: jwt(), refresh_token: 'refresh-new' }))
      .mockResolvedValueOnce(response(503));
    expect(await useAuthStore.getState().checkAuth()).toBe(true);
    expect(useAuthStore.getState().refreshToken).toBe('refresh-new');
  });

  it('authFetch keeps credentials when refresh is unavailable', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(401)).mockResolvedValueOnce(response(503));
    expect((await authFetch('/api/workspaces')).status).toBe(401);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('renews an expired token before sending an API request', async () => {
    useAuthStore.setState({ token: 'expired' });
    vi.mocked(fetch).mockResolvedValueOnce(response(200, { access_token: 'fresh-token', refresh_token: 'refresh-new' }))
      .mockResolvedValueOnce(response(200));
    expect((await authFetch('/api/workspaces')).status).toBe(200);
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain('/api/auth/refresh');
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).get('Authorization')).toBe('Bearer fresh-token');
  });

  it('retries a late 401 using a token already renewed by another request', async () => {
    let finish!: (value: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }))
      .mockResolvedValueOnce(response(200));
    const pending = authFetch('/api/workspaces');
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    useAuthStore.setState({ token: 'already-renewed', refreshToken: 'refresh-new' });
    finish(response(401));
    expect((await pending).status).toBe(200);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).get('Authorization')).toBe('Bearer already-renewed');
  });

  it('does not restore a user after logout during /me validation', async () => {
    let finish!: (value: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    const pending = useAuthStore.getState().checkAuth();
    useAuthStore.getState().logout();
    finish(response(200, { id: '1' }));
    expect(await pending).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('logs out when the refresh credential is rejected', async () => {
    vi.mocked(fetch).mockResolvedValue(response(401));
    expect(await useAuthStore.getState().refreshAccessToken()).toBe(false);
    expect(useAuthStore.getState().refreshToken).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('does not restore a session after logout during refresh', async () => {
    let finish!: (value: Response) => void;
    vi.mocked(fetch).mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    const pending = useAuthStore.getState().refreshAccessToken();
    useAuthStore.getState().logout();
    finish(response(200, { access_token: jwt(), refresh_token: 'refresh-new' }));
    expect(await pending).toBe(false);
    expect(useAuthStore.getState().token).toBeNull();
  });

  it('adopts another tab rotation after obtaining the browser lock', async () => {
    vi.stubGlobal('navigator', { locks: { request: vi.fn(async (_name, callback) => {
      getSafeStorage().setItem('nexus-auth', JSON.stringify({ state: {
        token: 'other-token', refreshToken: 'other-refresh', isAuthenticated: true,
      } }));
      return callback();
    }) } });
    expect(await useAuthStore.getState().refreshAccessToken()).toBe(true);
    expect(fetch).not.toHaveBeenCalled();
    expect(useAuthStore.getState().token).toBe('other-token');
  });

  it('adopts explicit logout from another tab', () => {
    getSafeStorage().setItem('nexus-auth', JSON.stringify({ state: {
      token: null, refreshToken: null, user: null, isAuthenticated: false,
    } }));
    syncPersistedAuthSession();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().token).toBeNull();
  });
});
