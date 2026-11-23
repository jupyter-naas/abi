// @vitest-environment jsdom
import { act, createElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { createIamAdminApi } from '@/lib/iam-admin/api';
import { readIamAccess, useIamAccess } from '@/lib/iam-admin/use-access';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useSuperadminAccess } from '@/hooks/use-superadmin-access';
import { usePermissionCache, PERMISSION_TTL_MS, PermissionSessionChanged } from '@/lib/permission-cache';
import { clearViewFlag, setViewFlag } from '@/lib/view-flag';
import { authFetch, useAuthStore, type User } from './auth';

const api = vi.hoisted(() => ({ url: 'https://api.example.test' }));
vi.mock('@/lib/config', () => ({ getApiUrl: () => api.url }));

const person = (id: string): User => ({ id, email: `${id}@example.invalid`, name: id, createdAt: new Date() });
const answer = (actions: Record<string, boolean> = { 'iam:ListGroups': true }) => Response.json({ scope: 'abi:', actions });
let mounted: Mounted | null = null;
async function settle() {
  for (let i = 0; i < 3; i += 1) await mounted?.flush();
}
beforeEach(() => {
  api.url = 'https://api.example.test';
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  useAuthStore.setState({ user: person('one'), csrfToken: 'session-csrf-one', isAuthenticated: true });
  vi.stubGlobal('fetch', vi.fn(async () => answer()));
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('permissions over the authenticated session', () => {
  it('shares default API instances, the platform navigation and a remounted hook', async () => {
    function Readers() {
      const first = useIamAccess();
      const second = useIamAccess('abi:');
      const platform = usePlatformSettingsAccess();
      return createElement('p', null, `${first.can('iam:ListGroups')}/${second.can('iam:ListGroups')}/${platform.actions?.['iam:ListGroups']}`);
    }
    mounted = await mount(Readers, {});
    await vi.waitFor(async () => {
      await mounted!.flush();
      expect(mounted!.host.textContent).toBe('true/true/true');
    });
    expect(fetch).toHaveBeenCalledTimes(1);
    await mounted.unmount();
    mounted = await mount(Readers, {});
    await settle();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fetch).mock.calls[0][1]?.cache).toBe('no-store');
  });

  it('canonicalizes the platform and gives concurrent readers independent bodies', async () => {
    const first = createIamAdminApi();
    const second = createIamAdminApi();
    const results = await Promise.all([readIamAccess(first), readIamAccess(second, 'abi:')]);
    expect(results[0].actions).toEqual(results[1].actions);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('revalidates expired data on focus without showing the previous scope', async () => {
    const now = Date.now();
    vi.spyOn(Date, 'now').mockReturnValue(now);
    function Reader() {
      const { can } = useIamAccess();
      return createElement('p', null, String(can('iam:ListGroups')));
    }
    mounted = await mount(Reader, {});
    await settle();
    expect(mounted.host.textContent).toBe('true');
    vi.mocked(fetch).mockImplementation(async () => answer({}));
    vi.mocked(Date.now).mockReturnValue(now + PERMISSION_TTL_MS + 1);
    await act(async () => { window.dispatchEvent(new Event('focus')); });
    await settle();
    expect(mounted.host.textContent).toBe('false');
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('does not invalidate for profile edits, but resets for a new session of the same user', async () => {
    await authFetch('/api/iam/admin/access');
    useAuthStore.getState().setUser({ ...person('one'), name: 'Updated profile' });
    await authFetch('/api/iam/admin/access');
    expect(fetch).toHaveBeenCalledTimes(1);
    useAuthStore.setState({ csrfToken: 'session-csrf-two' });
    await authFetch('/api/iam/admin/access');
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(usePermissionCache.getState().identity).not.toContain('session-csrf');
  });

  it('rejects late reads after logout and an A-B-A user switch', async () => {
    let finish!: (response: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve; }));
    const old = authFetch('/api/iam/admin/access');
    const rejected = expect(old).rejects.toBeInstanceOf(PermissionSessionChanged);
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
    useAuthStore.setState({ user: person('two') });
    useAuthStore.setState({ user: person('one') });
    vi.mocked(fetch).mockImplementation(async () => answer({}));
    expect((await (await authFetch('/api/iam/admin/access')).json()).actions).toEqual({});
    finish(answer({ 'iam:DeletePolicy': true }));
    await rejected;
    useAuthStore.getState().logout();
    expect(usePermissionCache.getState().entries.size).toBe(0);
    expect(usePermissionCache.getState().enabled).toBe(false);
  });

  it('isolates API origins and discards an older API response', async () => {
    let finish!: (response: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve; }));
    const old = readIamAccess(createIamAdminApi());
    const rejected = expect(old).rejects.toBeInstanceOf(PermissionSessionChanged);
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
    api.url = 'https://other-api.example.test';
    await readIamAccess(createIamAdminApi());
    finish(answer());
    await rejected;
    expect(vi.mocked(fetch).mock.calls[1][0]).toBe(`${api.url}/api/iam/admin/access`);
  });

  it('forgets viewer permissions before entering a view and forgets the person before leaving it', async () => {
    await authFetch('/api/iam/admin/access');
    const view = {
      person: { id: 'iam-person', name: 'Person' }, workspace: { id: 'w', name: 'Workspace' },
      ends_at: new Date(Date.now() + 60_000).toISOString(), groups_from: null,
    };
    setViewFlag({ workspaceId: 'w', returnTo: null }, view.ends_at);
    expect(usePermissionCache.getState().entries.size).toBe(0);
    expect(usePermissionCache.getState().enabled).toBe(false);
    useAuthStore.setState({ user: person('person-alias'), viewer: person('one'), view });
    vi.mocked(fetch).mockImplementation(async () => answer({}));
    expect((await (await authFetch('/api/iam/admin/access?scope=workspace')).json()).actions).toEqual({});
    expect(usePermissionCache.getState().enabled).toBe(true);
    clearViewFlag();
    expect(usePermissionCache.getState().enabled).toBe(false);
    useAuthStore.setState({ user: person('one'), viewer: null, view: null });
    vi.mocked(fetch).mockImplementation(async () => answer());
    expect((await (await authFetch('/api/iam/admin/access')).json()).actions['iam:ListGroups']).toBe(true);
  });

  it('keeps validation/simulation/sync from evicting permissions, but invalidates successful IAM writes', async () => {
    await authFetch('/api/iam/admin/access');
    for (const url of ['/api/iam/admin/policies/validate', '/api/iam/admin/simulate', '/api/agents/sync']) {
      await authFetch(url, { method: 'POST' });
      await authFetch('/api/iam/admin/access');
    }
    const reads = () => vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/api/iam/admin/access'));
    expect(reads()).toHaveLength(1);
    await authFetch('/api/iam/admin/groups', { method: 'POST' });
    await authFetch('/api/iam/admin/access');
    expect(reads()).toHaveLength(2);
  });

  it('bypasses restricted credentials and leaves ordinary business reads live', async () => {
    await authFetch('/api/iam/admin/access');
    await authFetch('/api/iam/admin/access', { headers: { Authorization: 'Bearer restricted-test-key' } });
    await authFetch('/api/agents');
    await authFetch('/api/agents');
    await authFetch('/api/iam/admin/access');
    expect(fetch).toHaveBeenCalledTimes(4);
    expect(usePermissionCache.getState().identity).not.toContain('restricted-test-key');
  });

  it('does not persist permission answers or session secrets', async () => {
    vi.mocked(fetch).mockImplementation(async () => answer({ 'permission-cache-marker': true }));
    await authFetch('/api/iam/admin/access');
    const stored = Array.from({ length: localStorage.length }, (_, i) => localStorage.getItem(localStorage.key(i)!)).join('\n');
    expect(stored).not.toContain('permission-cache-marker');
    expect(stored).not.toContain('session-csrf-one');
  });

  it('shares the Events read decision without turning ReadSystem into superadmin access', async () => {
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).endsWith('/admin/me')) return Response.json({ is_superadmin: false });
      if (String(url).endsWith('/events/types')) return Response.json([]);
      return answer({ 'nexus:ReadSystem': true });
    });
    function Reader() {
      const platform = usePlatformSettingsAccess();
      const services = useSuperadminAccess();
      return createElement('p', null, `${services}/${platform.actions?.['nexus:ReadSystem']}`);
    }
    mounted = await mount(Reader, {});
    await vi.waitFor(async () => {
      await mounted!.flush();
      expect(mounted!.host.textContent).toBe('denied/true');
    });
    const { useEventsStore } = await import('./events');
    await Promise.all([useEventsStore.getState().checkAccess(), useEventsStore.getState().checkAccess()]);
    expect(useEventsStore.getState().authState).toBe('authorized');
    const urls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
    expect(urls.filter((url) => url.endsWith('/iam/admin/access'))).toHaveLength(1);
    expect(urls.some((url) => url.endsWith('/admin/ping'))).toBe(false);
    expect(urls.filter((url) => url.endsWith('/events/types'))).toHaveLength(1);
  });

  it('discards Events metadata and old in-flight answers on identity change', async () => {
    const { useEventsStore } = await import('./events');
    let finish!: (response: Response) => void;
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).endsWith('/events/types')) return new Promise<Response>((resolve) => { finish = resolve; });
      return answer({ 'nexus:ReadSystem': true });
    });
    const checking = useEventsStore.getState().checkAccess();
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
    useEventsStore.setState({ search: 'previous-private-filter' });
    useAuthStore.setState({ user: person('two') });
    finish(Response.json([{ uri: 'old', label: 'Old' }]));
    await checking;
    expect(useEventsStore.getState()).toMatchObject({ authState: 'checking', availableTypes: [], events: [], search: '' });
  });
});
