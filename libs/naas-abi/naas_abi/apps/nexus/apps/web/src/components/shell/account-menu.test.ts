// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const state = vi.hoisted(() => ({
  user: 'olivia',
  answers: {} as Record<string, unknown>,
  opensWorkspaceSettings: false,
  hang: false,
  platformStatus: 'ready' as 'ready' | 'checking',
}));

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: () => undefined }) }));
vi.mock('@/hooks/use-platform-settings-access', () => ({
  usePlatformSettingsAccess: () => ({
    status: state.platformStatus,
    actions: state.platformStatus === 'ready' ? {} : null,
    retry: () => undefined,
  }),
}));
vi.mock('@/hooks/use-workspace-settings-access', () => ({
  useOpensWorkspaceSettings: () => state.opensWorkspaceSettings,
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { id: state.user }, logout: () => undefined }),
  authFetch: async (url: string) =>
    state.hang
      ? new Promise<Response>(() => undefined)
      : url in state.answers
      ? new Response(JSON.stringify(state.answers[url]), { status: 200 })
      : new Response('{}', { status: 403 }),
}));

import { useWorkspaceStore } from '@/stores/workspace';
import { AccountMenuPanel } from './account-menu';

const ACCESS_ACME = `/api/iam/admin/access?scope=${encodeURIComponent('abi:nexus:organization/acme')}`;

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  state.opensWorkspaceSettings = false;
  state.hang = false;
  state.platformStatus = 'ready';
});

async function menuFor(user: string, orgRole: string, focusFirstItem = false): Promise<HTMLElement> {
  state.user = user;
  state.answers = {
    '/api/organizations': [{ id: 'acme', name: 'Acme', current_user_role: orgRole }],
    [ACCESS_ACME]: { actions: { 'iam:ListPolicies': false } },
  };
  mounted = await mount(AccountMenuPanel, {
    user: { name: user, email: `${user}@example.com` },
    onClose: () => undefined,
    focusFirstItem,
  });
  await mounted.flush();
  await mounted.flush();
  return mounted.host;
}

function organizationLink(menu: HTMLElement): HTMLAnchorElement | null {
  return menu.querySelector<HTMLAnchorElement>('a[href^="/organizations/acme/settings"]');
}

describe('the account menu', () => {
  it('links Organization to an organization admin', async () => {
    const link = organizationLink(await menuFor('olivia', 'admin'));
    expect(link?.textContent).toContain('Organization');
  });
  it('hides it from a workspace owner who is a member of the organization', async () => {
    const menu = await menuFor('bob', 'member');
    expect(organizationLink(menu)).toBeNull();
    expect(menu.textContent).toContain('Account');
  });
});

function items(menu: HTMLElement): string[] {
  return [...menu.querySelectorAll('[role="menuitem"] .account-menu-item-label')].map(
    (el) => el.textContent?.trim() ?? '',
  );
}

describe('Infrastructure in the account menu', () => {
  it('sits between Account and Organization for whoever opens the workspace settings', async () => {
    useWorkspaceStore.setState({ currentWorkspaceId: 'ws-1' });
    state.opensWorkspaceSettings = true;
    const menu = await menuFor('olivia', 'admin');
    const link = menu.querySelector<HTMLAnchorElement>('a[href$="/settings/infrastructure"]');
    expect(link?.getAttribute('href')).toContain('ws-1');
    expect(items(menu)).toEqual(['Account', 'Infrastructure', 'Organization', 'Help', 'Log out']);
  });

  it('is not there for anyone else', async () => {
    useWorkspaceStore.setState({ currentWorkspaceId: 'ws-1' });
    const menu = await menuFor('bob', 'member');
    expect(items(menu)).not.toContain('Infrastructure');
    expect(items(menu)).toContain('Help');
  });
});

describe('what a settings row opens', () => {
  it('names the workspace and the organization', async () => {
    useWorkspaceStore.setState({
      currentWorkspaceId: 'ws-1',
      workspaces: [{ id: 'ws-1', name: 'JOE', organizationId: 'acme' }] as never,
    });
    state.opensWorkspaceSettings = true;
    const menu = await menuFor('olivia', 'admin');
    const detail = (href: string) =>
      menu.querySelector(`a[href${href}] .account-menu-item-detail`)?.textContent;
    expect(detail('$="/settings/infrastructure"')).toBe('JOE');
    expect(detail('^="/organizations/acme/settings"')).toBe('Acme');
    useWorkspaceStore.setState({ workspaces: [] });
  });
});

describe('the account menu from the keyboard', () => {
  function press(key: string) {
    document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  }
  const focused = () => document.activeElement?.querySelector('.account-menu-item-label')?.textContent;

  it('holds focus itself when a pointer opens it, and ArrowDown enters the rows', async () => {
    const menu = await menuFor('bob', 'member');
    expect(document.activeElement).toBe(menu.querySelector('[role="menu"]'));
    press('ArrowDown');
    expect(focused()).toBe('Account');
  });

  it('opens on its first item from the keyboard and the arrows go round', async () => {
    await menuFor('bob', 'member', true);
    expect(focused()).toBe('Account');
    press('ArrowDown');
    expect(focused()).toBe('Help');
    press('End');
    expect(focused()).toBe('Log out');
    press('ArrowDown');
    expect(focused()).toBe('Account');
    press('ArrowUp');
    expect(focused()).toBe('Log out');
    press('Home');
    expect(focused()).toBe('Account');
  });

  it('skips the rows whose access is still read', async () => {
    state.hang = true;
    state.platformStatus = 'checking';
    await menuFor('carol', 'admin', true);
    press('ArrowDown');
    expect(focused()).toBe('Help');
  });
});

describe('the settings entries while their access is read', () => {
  it('shows Organization and Platform as busy rows, not links, until they answer', async () => {
    state.hang = true;
    state.platformStatus = 'checking';
    const menu = await menuFor('carol', 'admin');
    const busy = [...menu.querySelectorAll('[aria-busy="true"]')].map((el) => el.textContent?.trim());
    expect(busy).toEqual(['Organization', 'Platform']);
    expect(menu.querySelector('a[href^="/organizations/"]')).toBeNull();
  });
});
