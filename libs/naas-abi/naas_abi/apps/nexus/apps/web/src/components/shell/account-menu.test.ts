// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const state = vi.hoisted(() => ({
  workspaceAccess: 'none' as 'all' | 'iam' | 'none' | 'unknown',
  platformStatus: 'ready' as 'ready' | 'checking',
  platformActions: {} as Record<string, boolean>,
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
    actions: state.platformStatus === 'ready' ? state.platformActions : null,
    retry: () => undefined,
  }),
}));
vi.mock('@/hooks/use-workspace-settings-access', () => ({
  useWorkspaceSettingsAccess: () => state.workspaceAccess,
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) => select({ user: { id: 'olivia' }, logout: () => undefined }),
}));

import { useWorkspaceStore } from '@/stores/workspace';
import { rememberSettingsPath } from '@/lib/settings-scope-path';
import { AccountMenuPanel } from './account-menu';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  state.workspaceAccess = 'none';
  state.platformStatus = 'ready';
  state.platformActions = {};
  window.sessionStorage.clear();
});

async function menu(focusFirstItem = false): Promise<HTMLElement> {
  useWorkspaceStore.setState({ currentWorkspaceId: 'ws-1' });
  mounted = await mount(AccountMenuPanel, {
    user: { name: 'Olivia', email: 'olivia@example.com' },
    onClose: () => undefined,
    focusFirstItem,
  });
  await mounted.flush();
  return mounted.host;
}

function items(host: HTMLElement): string[] {
  return [...host.querySelectorAll('[role="menuitem"] .account-menu-item-label')].map(
    (el) => el.textContent?.trim() ?? '',
  );
}

const href = (host: HTMLElement, label: string) =>
  [...host.querySelectorAll<HTMLAnchorElement>('a[role="menuitem"]')].find((a) => a.textContent?.includes(label))
    ?.getAttribute('href');

describe('the account menu', () => {
  it('has one Settings door, not one per level', async () => {
    const host = await menu();
    expect(items(host)).toEqual(['Settings', 'Help', 'Log out']);
    expect(href(host, 'Settings')).toBe('/account/profile');
  });

  it('opens Settings on the workspace when the caller opens its settings', async () => {
    state.workspaceAccess = 'all';
    expect(href(await menu(), 'Settings')).toBe('/workspace/ws-1/settings/general');
  });

  it('reopens the last settings page, at any level, but not another workspace\'s', async () => {
    rememberSettingsPath('settings', '/organizations/acme/settings/members');
    expect(href(await menu(), 'Settings')).toBe('/organizations/acme/settings/members');
    await mounted?.unmount();
    rememberSettingsPath('settings', '/workspace/ws-9/settings/general');
    expect(href(await menu(), 'Settings')).toBe('/account/profile');
  });

  it('shows the Console to whoever may watch the platform', async () => {
    state.platformActions = { 'nexus:ReadSystem': true };
    const host = await menu();
    expect(items(host)).toEqual(['Settings', 'Console', 'Help', 'Log out']);
    expect(href(host, 'Console')).toMatch(/^\/settings\/system/);
  });

  it('leaves the Console out for a platform administrator who may only set things', async () => {
    state.platformActions = { 'nexus:ListUsers': true };
    expect(items(await menu())).toEqual(['Settings', 'Help', 'Log out']);
  });
});

describe('the account menu from the keyboard', () => {
  function press(key: string) {
    document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  }
  const focused = () => document.activeElement?.querySelector('.account-menu-item-label')?.textContent;

  it('holds focus itself when a pointer opens it, and ArrowDown enters the rows', async () => {
    const host = await menu();
    expect(document.activeElement).toBe(host.querySelector('[role="menu"]'));
    press('ArrowDown');
    expect(focused()).toBe('Settings');
  });

  it('opens on its first item from the keyboard and the arrows go round', async () => {
    await menu(true);
    expect(focused()).toBe('Settings');
    press('ArrowDown');
    expect(focused()).toBe('Help');
    press('End');
    expect(focused()).toBe('Log out');
    press('ArrowDown');
    expect(focused()).toBe('Settings');
    press('ArrowUp');
    expect(focused()).toBe('Log out');
    press('Home');
    expect(focused()).toBe('Settings');
  });

  it('shows the Console as a busy row while the access is read, and skips it', async () => {
    state.platformStatus = 'checking';
    const host = await menu(true);
    const busy = [...host.querySelectorAll('[aria-busy="true"]')].map((el) => el.textContent?.trim());
    expect(busy).toEqual(['Console']);
    press('ArrowDown');
    expect(focused()).toBe('Help');
  });
});
