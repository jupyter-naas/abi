import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { authFetch, useAuthStore } from './auth';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));
const response = (status: number, body = {}) => new Response(JSON.stringify(body), { status });
const SESSION = {
  user: { id: '1', email: 'test@example.test', name: 'Test' },
  csrf_token: 'csrf-1',
};
const session = () => useAuthStore.setState({
  csrfToken: 'csrf-1', isAuthenticated: true,
  user: { id: '1', email: 'test@example.test', name: 'Test', createdAt: new Date() },
});

beforeEach(() => {
  session();
  vi.stubGlobal('fetch', vi.fn());
  vi.stubGlobal('document', { cookie: '' });
});
afterEach(() => vi.unstubAllGlobals());

describe('session check', () => {
  it('re-reads the session the API holds', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(200, SESSION));
    expect(await useAuthStore.getState().checkAuth()).toBe(true);
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe('https://api.example.test/api/auth/oidc/session');
    expect(useAuthStore.getState().csrfToken).toBe('csrf-1');
  });

  it.each([429, 500, 502, 503])('keeps the session after HTTP %s', async (status) => {
    vi.mocked(fetch).mockResolvedValue(response(status));
    expect(await useAuthStore.getState().checkAuth()).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('keeps the session when offline', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('offline'));
    expect(await useAuthStore.getState().checkAuth()).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('ends the session the API no longer knows', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(401));
    expect(await useAuthStore.getState().checkAuth()).toBe(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });
});

describe('authFetch', () => {
  it('keeps the session when the API fails after a 401 re-read', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(401)).mockResolvedValueOnce(response(503));
    expect((await authFetch('/api/workspaces')).status).toBe(401);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('ends the session when the API no longer knows it', async () => {
    vi.stubGlobal('window', { location: { pathname: '/workspace/w', href: '' } });
    vi.mocked(fetch)
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(401)) // /session
      .mockResolvedValue(response(200, { status: 'logged out' })); // logout
    expect((await authFetch('/api/workspaces')).status).toBe(401);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('retries a request once the session is re-read', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, SESSION))
      .mockResolvedValueOnce(response(200));
    expect((await authFetch('/api/workspaces')).status).toBe(200);
    expect(fetch).toHaveBeenCalledTimes(3);
  });
});
