// @vitest-environment jsdom
/**
 * The session store during a view ("View as"): `view` comes from `/session`, the pages show the
 * person (the server answers `/api/auth/me` as them) while the session stays the viewer's, the
 * browser and the server agree on a view before anything is shown, and the server's refusals
 * reach the page as the server wrote them.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { authFetch, useAuthStore } from './auth';
import { clearViewFlag, readViewFlag, setViewFlag } from '@/lib/view-flag';
import { navigation, onViewRefusal } from '@/lib/view-model';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

const json = (status: number, body: unknown = {}) => new Response(JSON.stringify(body), { status });
const VIEWER = { id: 'usr_root', email: 'admin@example.com', name: 'Root' };
const PERSON = { id: 'usr_carol', email: 'carol@example.com', name: 'Carol' };
const VIEW = {
  person: { id: 'iam_carol', name: 'Carol' },
  workspace: { id: 'ws-alpha', name: 'Alpha' },
  ends_at: new Date(Date.now() + 15 * 60_000).toISOString(),
  groups_from: null,
};
const session = (view: unknown = null) => ({ user: VIEWER, csrf_token: 'csrf-root', provider: 'idp', view });

let reload: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false, provider: null });
  vi.stubGlobal('fetch', vi.fn());
  reload = vi.spyOn(navigation, 'reload').mockImplementation(() => undefined);
});
afterEach(() => {
  clearViewFlag();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('reading the view from the session', () => {
  it('shows the person, keeps the viewer’s session, and notes where the groups come from', async () => {
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, VIEW.ends_at);
    vi.mocked(fetch).mockResolvedValueOnce(json(200, session(VIEW))).mockResolvedValueOnce(json(200, PERSON));
    expect(await useAuthStore.getState().adoptCookieSession()).toBe(true);
    const state = useAuthStore.getState();
    expect(state.view).toEqual(VIEW);
    expect(state.user?.name).toBe('Carol');
    expect(state.viewer?.name).toBe('Root');
    expect(state.csrfToken).toBe('csrf-root');
    expect(state.provider).toBe('idp');
    expect(String(vi.mocked(fetch).mock.calls[1][0])).toBe('https://api.example.test/api/auth/me');
    expect(reload).not.toHaveBeenCalled();
  });

  it('never shows the viewer as the person when the person cannot be read', async () => {
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, VIEW.ends_at);
    vi.mocked(fetch).mockResolvedValueOnce(json(200, session(VIEW))).mockResolvedValueOnce(json(503));
    await useAuthStore.getState().adoptCookieSession();
    expect(useAuthStore.getState().user?.name).toBe('Carol');
    expect(useAuthStore.getState().user?.email).toBe('');
  });

  it('has no view outside one', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(json(200, session(null)));
    await useAuthStore.getState().adoptCookieSession();
    expect(useAuthStore.getState().view).toBeNull();
    expect(useAuthStore.getState().user?.name).toBe('Root');
    expect(useAuthStore.getState().viewer).toBeNull();
  });

  it('reloads with the flag raised for a view this browser did not know', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(json(200, session(VIEW)));
    await useAuthStore.getState().adoptCookieSession();
    expect(readViewFlag()?.workspaceId).toBe('ws-alpha');
    expect(reload).toHaveBeenCalledOnce();
    // nothing of the viewer or the person is shown by this load
    expect(useAuthStore.getState().view).toBeNull();
  });

  it('reloads with the flag cleared when the view has ended on the server', async () => {
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, VIEW.ends_at);
    vi.mocked(fetch).mockResolvedValueOnce(json(200, session(null)));
    await useAuthStore.getState().adoptCookieSession();
    expect(readViewFlag()).toBeNull();
    expect(reload).toHaveBeenCalledOnce();
  });

  it('forgets the view with the sign-in', async () => {
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, VIEW.ends_at);
    vi.mocked(fetch).mockResolvedValueOnce(json(401));
    await useAuthStore.getState().adoptCookieSession();
    expect(readViewFlag()).toBeNull();
  });
});

describe('the server’s refusals', () => {
  const inView = () => {
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, VIEW.ends_at);
    useAuthStore.setState({ view: VIEW, csrfToken: 'csrf-root', isAuthenticated: true, user: { ...PERSON, createdAt: new Date() } });
  };

  it.each([
    ['Read-only: you are viewing as Carol', 'POST'],
    ['Outside this view: you are viewing as Carol in Alpha', 'GET'],
  ])('shows "%s" as the server worded it, without a second request', async (detail, method) => {
    inView();
    const shown: string[] = [];
    const off = onViewRefusal((message) => shown.push(message));
    vi.mocked(fetch).mockResolvedValue(json(403, { detail }));
    const response = await authFetch('/api/chat/messages', { method });
    off();
    expect(response.status).toBe(403);
    expect(shown).toEqual([detail]);
    expect(fetch).toHaveBeenCalledTimes(1);
    // the body is still readable by the caller
    expect((await response.json()).detail).toBe(detail);
  });

  it('shows no toast for another 403, nor outside a view', async () => {
    inView();
    const shown: string[] = [];
    const off = onViewRefusal((message) => shown.push(message));
    vi.mocked(fetch).mockResolvedValue(json(403, { detail: 'You do not have permission' }));
    await authFetch('/api/x');
    useAuthStore.setState({ view: null });
    vi.mocked(fetch).mockResolvedValue(json(403, { detail: 'Read-only: you are viewing as Carol' }));
    await authFetch('/api/x');
    off();
    expect(shown).toEqual([]);
  });
});

describe('signing out in a view', () => {
  it('clears the browser’s own stores, not the memory the view runs on, and drops the view', () => {
    const real = { removeItem: vi.fn() };
    (window as unknown as { __nexusRealLocalStorage: unknown }).__nexusRealLocalStorage = real;
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, VIEW.ends_at);
    useAuthStore.setState({ view: VIEW, viewer: { ...VIEWER, createdAt: new Date() }, isAuthenticated: true });
    vi.mocked(fetch).mockResolvedValue(json(200, {}));
    useAuthStore.getState().logout();
    delete (window as unknown as { __nexusRealLocalStorage?: unknown }).__nexusRealLocalStorage;
    expect(real.removeItem).toHaveBeenCalledWith('nexus-workspace-storage');
    expect(real.removeItem).toHaveBeenCalledWith('nexus-agents');
    expect(readViewFlag()).toBeNull();
    expect(useAuthStore.getState().view).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });
});
