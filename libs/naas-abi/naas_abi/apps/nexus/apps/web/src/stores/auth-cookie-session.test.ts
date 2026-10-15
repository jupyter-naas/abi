import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// A sign-in through an identity provider: the API holds the session behind an
// httpOnly cookie; the web app keeps no token, and its CSRF token in memory only.

const storage = new Map<string, string>();
vi.mock('@/lib/safe-storage', () => ({
  getSafeStorage: () => ({
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => void storage.set(key, value),
    removeItem: (key: string) => void storage.delete(key),
  }),
}));
vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.test' }));

const { authFetch, getAuthHeader, hasSession, persistedAuthState, providerLoginUrl, useAuthStore } =
  await import('./auth');
const { safeNextPath } = await import('@/lib/auth-session');

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const SESSION = {
  user: { id: 'usr_01', email: 'ada@example.com', name: 'Ada' },
  csrf_token: 'csrf-123',
  provider: 'acme',
  refresh_at: '2026-10-15T12:10:00',
};

describe('a cookie session', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    storage.clear();
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('document', { cookie: '' });
    useAuthStore.setState({
      user: null,
      token: null,
      refreshToken: null,
      sessionKind: null,
      csrfToken: null,
      isAuthenticated: false,
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('is adopted from the API with the cookie, and persists no token', async () => {
    fetchMock.mockResolvedValueOnce(json(SESSION));
    expect(await useAuthStore.getState().adoptCookieSession()).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.test/api/auth/oidc/session');
    expect(init.credentials).toBe('include');

    const state = useAuthStore.getState();
    expect(state.sessionKind).toBe('cookie');
    expect(state.csrfToken).toBe('csrf-123');
    expect(hasSession()).toBe(true);
    const persisted = storage.get('nexus-auth') ?? '';
    expect(persisted).not.toContain('csrf-123');
    expect(JSON.parse(persisted).state).toEqual({
      user: SESSION.user,
      sessionKind: 'cookie',
      isAuthenticated: true,
    });
  });

  it('sends the cookie, and the CSRF token on changes only', async () => {
    useAuthStore.setState({ sessionKind: 'cookie', csrfToken: 'csrf-123', isAuthenticated: true });
    fetchMock.mockResolvedValue(json({ ok: true }));
    await authFetch('/api/workspaces');
    await authFetch('/api/workspaces', { method: 'POST', body: '{}' });
    const [, read] = fetchMock.mock.calls[0];
    const [, write] = fetchMock.mock.calls[1];
    expect(read.credentials).toBe('include');
    expect(new Headers(read.headers).has('X-CSRF-Token')).toBe(false);
    expect(new Headers(read.headers).has('Authorization')).toBe(false);
    expect(write.credentials).toBe('include');
    expect(new Headers(write.headers).get('X-CSRF-Token')).toBe('csrf-123');
    expect(getAuthHeader('DELETE')).toEqual({ 'X-CSRF-Token': 'csrf-123' });
    expect(getAuthHeader('GET')).toEqual({});
  });

  it('is re-read once on a 401, then signed out', async () => {
    useAuthStore.setState({ sessionKind: 'cookie', csrfToken: 'csrf-123', isAuthenticated: true });
    vi.stubGlobal('window', { location: { pathname: '/workspace/w', href: '' } });
    fetchMock
      .mockResolvedValueOnce(json({ detail: 'Not authenticated' }, 401)) // the request
      .mockResolvedValueOnce(json({ detail: 'Not signed in' }, 401)) // /session
      .mockResolvedValue(json({ status: 'logged out' })); // logout
    const response = await authFetch('/api/workspaces');
    expect(response.status).toBe(401);
    expect(useAuthStore.getState().sessionKind).toBeNull();
    expect(hasSession()).toBe(false);
  });

  it('never persists a token for a cookie session, whatever is in memory', () => {
    const persisted = persistedAuthState({
      user: null,
      token: 'leaked',
      refreshToken: 'leaked',
      sessionKind: 'cookie',
      isAuthenticated: true,
    });
    expect(JSON.stringify(persisted)).not.toContain('leaked');
  });

  it('starts a sign-in at the API, with a path on this app to land on', () => {
    expect(providerLoginUrl({ provider: 'acme', email: 'a@acme.com', next: '/workspace/w' })).toBe(
      'https://api.test/api/auth/oidc/login?provider=acme&email=a%40acme.com&next=%2Fworkspace%2Fw',
    );
    expect(safeNextPath('/workspace/w/chat')).toBe('/workspace/w/chat');
    for (const unsafe of ['https://evil.test', '//evil.test', '/\\evil.test', null, '']) {
      expect(safeNextPath(unsafe)).toBe('/');
    }
  });
});
