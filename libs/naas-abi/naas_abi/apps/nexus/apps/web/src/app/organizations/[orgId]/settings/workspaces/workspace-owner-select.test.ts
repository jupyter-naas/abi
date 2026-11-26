// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { clearViewFlag, setViewFlag } from '@/lib/view-flag';
import { ownerMembersUrl, WorkspaceOwnerSelect } from './workspace-owner-select';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

// `authFetch` loads this on its first call: load it here, so the test need not wait for it.
beforeAll(async () => void (await import('@/stores/network-activity')));

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  clearViewFlag();
  vi.unstubAllGlobals();
});

const inView = () => setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, Date.now() + 15 * 60_000);

describe('where the owners of a workspace are read', () => {
  it('from the organization’s members, outside a view', () => {
    expect(ownerMembersUrl('acme', 'ws-alpha')).toBe('/api/organizations/acme/members');
  });

  it('from the workspace’s own members in a view: the organization’s people are outside it', () => {
    inView();
    expect(ownerMembersUrl('acme', 'ws-alpha')).toBe('/api/workspaces/ws-alpha/members');
  });
});

describe('the Owner picker', () => {
  it('names the current owner in a view without asking for the organization’s members', async () => {
    inView();
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify([{ user_id: 'usr_bob', email: 'bob@example.com', name: 'Bob' }]), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    mounted = await mount(WorkspaceOwnerSelect, {
      orgId: 'acme',
      workspaceId: 'ws-alpha',
      value: 'usr_bob',
      onChange: vi.fn(),
      disabled: true,
    });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await mounted.flush();
    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls).toEqual(['https://api.example.test/api/workspaces/ws-alpha/members']);
    expect(mounted.host.textContent).toContain('Bob · bob@example.com');
  });

  it('picks the workspace admin at creation, the creator by default', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify([
            { user_id: 'usr_me', email: 'me@example.com', name: 'Me' },
            { user_id: 'usr_ann', email: 'ann@example.com', name: 'Ann' },
          ]),
          { status: 200 },
        ),
    );
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    const onChange = vi.fn();
    mounted = await mount(WorkspaceOwnerSelect, { orgId: 'acme', value: 'usr_me', onChange, role: 'admin' as const });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await mounted.flush();
    const trigger = mounted.host.querySelector('button[aria-haspopup="listbox"]');
    expect(trigger?.getAttribute('aria-label')).toBe('Workspace admin: Me · me@example.com');
    expect(mounted.host.textContent).not.toContain('owner');
    await mounted.click(trigger);
    await mounted.flush();
    const ann = [...document.querySelectorAll('[role="option"]')].find((o) => o.textContent?.includes('Ann'));
    expect(document.querySelector('[role="listbox"]')?.getAttribute('aria-label')).toBe('Workspace admin');
    await mounted.click(ann ?? null);
    expect(onChange).toHaveBeenCalledWith('usr_ann');
  });
});
