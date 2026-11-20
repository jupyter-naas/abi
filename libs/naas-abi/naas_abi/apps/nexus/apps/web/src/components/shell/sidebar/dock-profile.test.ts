// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: () => undefined, replace: () => undefined }),
  usePathname: () => '/workspace/ws-1/home',
}));
vi.mock('@/hooks/use-avatar-settings-links', () => ({
  useWarmAvatarSettingsLinks: () => undefined,
  useSettingsHref: () => '/account/profile',
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { name: 'Dev Admin', email: 'admin@joe.com' }, logout: () => undefined }),
}));

import { useWorkspaceStore } from '@/stores/workspace';
import { DockProfile } from './dock-profile';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
  useWorkspaceStore.setState({ workspaces: [], currentWorkspaceId: null });
});

async function avatar(labeled: boolean): Promise<HTMLButtonElement | null> {
  mounted = await mount(DockProfile, { labeled });
  await mounted.flush();
  return mounted.host.querySelector('button');
}

describe('the avatar at the bottom of the dock', () => {
  it('shows the name and workspace, and opens the account menu', async () => {
    useWorkspaceStore.setState({
      workspaces: [{ id: 'ws-joe', name: 'JOE', currentUserRole: 'admin' }] as never,
      currentWorkspaceId: 'ws-joe',
    });
    const button = await avatar(true);
    expect(button?.tagName).toBe('BUTTON');
    expect(button?.getAttribute('href')).toBeNull();
    expect(button?.getAttribute('aria-haspopup')).toBe('menu');
    expect(button?.getAttribute('aria-label')).toBe('Dev Admin, account menu');
    expect(button?.textContent).toContain('Dev Admin');
    expect(button?.textContent).toContain('JOE');
    await mounted?.click(button);
    const menu = document.querySelector('[role="menu"]');
    expect(menu?.textContent).toContain('admin@joe.com');
    expect(menu?.textContent).not.toContain('Help');
  });

  it('opens the menu from the icon rail instead of linking straight to Account', async () => {
    const button = await avatar(false);
    expect(button?.getAttribute('aria-expanded')).toBe('false');
    await mounted?.click(button);
    expect(document.querySelector('[role="menu"]')).not.toBeNull();
    expect(mounted?.host.querySelector('a[href="/account/profile"]')).toBeNull();
  });
});
