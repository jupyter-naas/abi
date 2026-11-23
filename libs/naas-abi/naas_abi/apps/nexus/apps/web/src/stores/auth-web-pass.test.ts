import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The session and this host's web pass begin and end together.

const pass = vi.hoisted(() => ({ keep: vi.fn(), drop: vi.fn() }));
vi.mock('@/lib/web-pass', () => ({ keepWebPass: pass.keep, dropWebPass: pass.drop }));
vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.test' }));
vi.mock('@/lib/safe-storage', () => ({
  getSafeStorage: () => ({ getItem: () => null, setItem: () => undefined, removeItem: () => undefined }),
}));

const { useAuthStore } = await import('./auth');

describe('the web pass follows the session', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    pass.keep.mockReset();
    pass.drop.mockReset();
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('document', { cookie: '' });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('keeps a pass while the session lives', async () => {
    fetchMock.mockResolvedValueOnce(
      Response.json({ user: { id: 'usr_01', email: 'a@example.com', name: 'A' }, csrf_token: 'c', provider: 'p' }),
    );
    expect(await useAuthStore.getState().adoptCookieSession()).toBe(true);
    expect(pass.keep).toHaveBeenCalledWith('https://api.test', expect.any(Function));
    expect(pass.drop).not.toHaveBeenCalled();
  });

  it('keeps no pass once the session is gone', async () => {
    useAuthStore.setState({ isAuthenticated: true });
    fetchMock.mockResolvedValueOnce(Response.json({ detail: 'Not signed in' }, { status: 401 }));
    expect(await useAuthStore.getState().adoptCookieSession()).toBe(false);
    expect(pass.drop).toHaveBeenCalled();

    // Signed out in another tab while this one was never signed in: dropped too.
    pass.drop.mockReset();
    useAuthStore.setState({ isAuthenticated: false });
    fetchMock.mockResolvedValueOnce(Response.json({ detail: 'Not signed in' }, { status: 401 }));
    await useAuthStore.getState().adoptCookieSession();
    expect(pass.drop).toHaveBeenCalled();
  });
});
