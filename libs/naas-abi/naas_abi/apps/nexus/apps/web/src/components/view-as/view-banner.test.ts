// @vitest-environment jsdom
/**
 * The banner of a view: who is viewed, where, the time left, the groups note, Stop, the reload by
 * itself at the end, and the server's refusals as toasts.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { clearViewFlag, readViewFlag, setViewFlag } from '@/lib/view-flag';
import { announceViewRefusal, navigation, type ViewAs } from '@/lib/view-model';
import { useAuthStore } from '@/stores/auth';
import { ViewBanner } from './view-banner';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

const NOW = new Date('2026-11-06T10:00:00Z').getTime();
const view = (over: Partial<ViewAs> = {}): ViewAs => ({
  person: { id: 'iam_dave', name: 'Dave' },
  workspace: { id: 'ws-alpha', name: 'Alpha' },
  ends_at: new Date(NOW + 12 * 60_000 + 30_000).toISOString(),
  groups_from: '2026-11-05T09:00:00+00:00',
  ...over,
});

// `authFetch` loads this on its first call: load it here, so no test depends on the order of the others.
beforeAll(async () => void (await import('@/stores/network-activity')));

const session = (view: unknown) => new Response(JSON.stringify({ user: {}, csrf_token: 'c', view }), { status: 200 });

let mounted: Mounted | null = null;
let go: ReturnType<typeof vi.spyOn>;
let reload: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.useFakeTimers({ now: NOW, toFake: ['Date', 'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] });
  go = vi.spyOn(navigation, 'go').mockImplementation(() => undefined);
  reload = vi.spyOn(navigation, 'reload').mockImplementation(() => undefined);
  useAuthStore.setState({ view: null, provider: 'google', csrfToken: 'csrf' });
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  clearViewFlag();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  useAuthStore.setState({ view: null, provider: null, csrfToken: null });
});

const settle = () => act(async () => void (await vi.advanceTimersByTimeAsync(0)));
const text = () => mounted!.host.textContent ?? '';

describe('the banner', () => {
  it('shows nothing outside a view', async () => {
    mounted = await mount(ViewBanner, {});
    expect(mounted.host.querySelector('[data-view-banner]')).toBeNull();
  });

  it('says who is viewed, where, and how long is left', async () => {
    useAuthStore.setState({ view: view() });
    mounted = await mount(ViewBanner, {});
    expect(text()).toContain('Viewing as Dave (read-only) in Alpha');
    expect(text()).toContain('13 min left');
    expect(text()).not.toContain('without');
    expect(text()).toContain('Stop');
  });

  it('counts the minutes down', async () => {
    useAuthStore.setState({ view: view() });
    mounted = await mount(ViewBanner, {});
    await act(async () => void vi.advanceTimersByTime(60_000 * 6));
    expect(text()).toContain('7 min left');
  });

  it('says the provider’s groups are missing when none were recorded', async () => {
    useAuthStore.setState({ view: view({ groups_from: null }) });
    mounted = await mount(ViewBanner, {});
    expect(text()).toContain('without google groups');
  });

  it('reloads by itself at the end, once the server says the view is over', async () => {
    useAuthStore.setState({ view: view() });
    const fetchMock = vi.fn(async () => session(null));
    vi.stubGlobal('fetch', fetchMock);
    mounted = await mount(ViewBanner, {});
    await act(async () => void vi.advanceTimersByTime(12 * 60_000));
    expect(reload).not.toHaveBeenCalled();
    await act(async () => void (await vi.advanceTimersByTimeAsync(31_000)));
    expect(String(fetchMock.mock.calls[0][0])).toBe('https://api.example.test/api/auth/oidc/session');
    expect(reload).toHaveBeenCalledOnce();
    expect(readViewFlag()).toBeNull();
  });

  it('does not reload while the server’s view still runs (the browser’s clock is ahead)', async () => {
    useAuthStore.setState({ view: view() });
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, view().ends_at);
    let running = true;
    const fetchMock = vi.fn(async () => session(running ? view() : null));
    vi.stubGlobal('fetch', fetchMock);
    mounted = await mount(ViewBanner, {});
    await act(async () => void (await vi.advanceTimersByTimeAsync(13 * 60_000)));
    // reads the session at the end, then every few seconds: no reload, and the flag stays
    await act(async () => void (await vi.advanceTimersByTimeAsync(20_000)));
    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(3);
    expect(reload).not.toHaveBeenCalled();
    expect(readViewFlag()).not.toBeNull();
    running = false;
    await act(async () => void (await vi.advanceTimersByTimeAsync(6_000)));
    expect(reload).toHaveBeenCalledOnce();
    expect(readViewFlag()).toBeNull();
  });

  it('does not reload when the session cannot be read', async () => {
    useAuthStore.setState({ view: view() });
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 503 })));
    mounted = await mount(ViewBanner, {});
    await act(async () => void (await vi.advanceTimersByTimeAsync(13 * 60_000 + 12_000)));
    expect(reload).not.toHaveBeenCalled();
  });

  it('Stop ends the view and loads the page it was started from', async () => {
    useAuthStore.setState({ view: view() });
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: '/settings/roles?section=people&person=iam_dave' }, view().ends_at);
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ stopped: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    mounted = await mount(ViewBanner, {});
    await mounted.click(mounted.host.querySelector('.view-banner-stop'));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await settle();
    expect(fetchMock.mock.calls[0][0]).toBe('https://api.example.test/api/iam/view-as');
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('X-CSRF-Token')).toBe('csrf');
    expect(readViewFlag()).toBeNull();
    expect(go).toHaveBeenCalledWith('/settings/roles?section=people&person=iam_dave');
  });

  it('Stop falls back to the person’s page in the viewed workspace', async () => {
    useAuthStore.setState({ view: view() });
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, view().ends_at);
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    mounted = await mount(ViewBanner, {});
    await mounted.click(mounted.host.querySelector('.view-banner-stop'));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await settle();
    expect(go).toHaveBeenCalledWith('/workspace/ws-alpha/settings/permissions?section=people&person=iam_dave');
  });

  it('stays in the view and says why when Stop fails', async () => {
    useAuthStore.setState({ view: view() });
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: '/x' }, view().ends_at);
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ detail: 'try again' }), { status: 503 }));
    vi.stubGlobal('fetch', fetchMock);
    mounted = await mount(ViewBanner, {});
    await mounted.click(mounted.host.querySelector('.view-banner-stop'));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await settle();
    expect(go).not.toHaveBeenCalled();
    expect(readViewFlag()).not.toBeNull();
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toBe('try again');
  });

  it('shows the server’s refusal as a toast, as it worded it', async () => {
    useAuthStore.setState({ view: view() });
    mounted = await mount(ViewBanner, {});
    await act(async () => announceViewRefusal('Read-only: you are viewing as Dave'));
    expect(mounted.host.querySelector('[data-view-toast]')?.textContent).toBe('Read-only: you are viewing as Dave');
    await act(async () => void vi.advanceTimersByTime(9_000));
    expect(mounted.host.querySelector('[data-view-toast]')).toBeNull();
  });

  it('shows the same refusal once, however many calls the page made', async () => {
    useAuthStore.setState({ view: view() });
    mounted = await mount(ViewBanner, {});
    const outside = 'Outside this view: you are viewing as Dave in Alpha';
    await act(async () => {
      announceViewRefusal(outside);
      announceViewRefusal(outside);
      announceViewRefusal(outside);
    });
    expect(mounted.host.querySelectorAll('[data-view-toast]')).toHaveLength(1);
    // A different refusal is its own notice.
    await act(async () => announceViewRefusal('Read-only: you are viewing as Dave'));
    expect(mounted.host.querySelectorAll('[data-view-toast]')).toHaveLength(2);
    // The same one again, while it still shows, stays one and lives on from the last call.
    await act(async () => void vi.advanceTimersByTime(6_000));
    await act(async () => announceViewRefusal(outside));
    expect(mounted.host.querySelectorAll('[data-view-toast]')).toHaveLength(2);
    await act(async () => void vi.advanceTimersByTime(6_000));
    expect(mounted.host.querySelectorAll('[data-view-toast]')).toHaveLength(1);
    expect(mounted.host.querySelector('[data-view-toast]')?.textContent).toBe(outside);
  });
});
