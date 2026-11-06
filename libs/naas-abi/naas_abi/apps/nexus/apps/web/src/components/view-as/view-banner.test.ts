// @vitest-environment jsdom
/**
 * The banner of a view: who is viewed, where, the time left, the groups note, Stop, the reload by
 * itself at the end, and the server's refusals as toasts.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

  it('reloads by itself at the end', async () => {
    useAuthStore.setState({ view: view() });
    mounted = await mount(ViewBanner, {});
    await act(async () => void vi.advanceTimersByTime(12 * 60_000));
    expect(reload).not.toHaveBeenCalled();
    await act(async () => void vi.advanceTimersByTime(31_000));
    expect(reload).toHaveBeenCalledOnce();
  });

  it('Stop ends the view and loads the page it was started from', async () => {
    useAuthStore.setState({ view: view() });
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: '/settings/roles?section=people&person=iam_dave' }, view().ends_at);
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ stopped: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    mounted = await mount(ViewBanner, {});
    await mounted.click(mounted.host.querySelector('.view-banner-stop'));
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
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })));
    mounted = await mount(ViewBanner, {});
    await mounted.click(mounted.host.querySelector('.view-banner-stop'));
    await settle();
    expect(go).toHaveBeenCalledWith('/workspace/ws-alpha/settings/permissions?section=people&person=iam_dave');
  });

  it('stays in the view and says why when Stop fails', async () => {
    useAuthStore.setState({ view: view() });
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: '/x' }, view().ends_at);
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'try again' }), { status: 503 })));
    mounted = await mount(ViewBanner, {});
    await mounted.click(mounted.host.querySelector('.view-banner-stop'));
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
});
