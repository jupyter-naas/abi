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
  usePathname: () => '/workspace/ws-1/files',
}));
vi.mock('@/hooks/use-avatar-settings-links', () => ({
  useWarmAvatarSettingsLinks: () => undefined,
  useSettingsHref: () => '/workspace/ws-1/settings/general',
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { name: 'Dev Admin', email: 'admin@joe.com' }, logout: () => undefined }),
}));

import { MobileTopBar } from './mobile-top-bar';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

const accountButton = (host: HTMLElement) =>
  host.querySelector<HTMLButtonElement>('button[aria-haspopup="menu"]');

describe('the phone top bar', () => {
  it('opens the account menu from the avatar', async () => {
    mounted = await mount(MobileTopBar, { variant: 'top', title: 'Files' });
    await mounted.flush();
    const button = accountButton(mounted.host);
    expect(button?.getAttribute('aria-label')).toBe('Dev Admin, account menu');
    expect(mounted.host.querySelector('a[href="/account/profile"]')).toBeNull();
    await mounted.click(button);
    const menu = document.querySelector('[role="menu"]');
    expect(menu?.textContent).toContain('Find workspace');
    expect(menu?.textContent).toContain('Log out');
    expect(menu?.textContent).not.toContain('Help');
    expect(menu?.querySelector('a[href="/account/profile"]')?.textContent).toContain('Account');
  });

  it('leaves the avatar out of a detail view', async () => {
    mounted = await mount(MobileTopBar, { variant: 'detail', title: 'Thread' });
    expect(accountButton(mounted.host)).toBeNull();
  });
});
