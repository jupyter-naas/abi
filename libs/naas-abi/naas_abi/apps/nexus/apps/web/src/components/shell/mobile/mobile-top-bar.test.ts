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
vi.mock('@/hooks/use-avatar-settings-links', () => ({ useWarmAvatarSettingsLinks: () => undefined }));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { name: 'Dev Admin', email: 'admin@joe.com' } }),
}));

import { MobileTopBar } from './mobile-top-bar';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

const accountLink = (host: HTMLElement) => host.querySelector<HTMLAnchorElement>('a[href="/account/profile"]');

describe('the phone top bar', () => {
  it('has the avatar open Settings on the Account tab, with no popup', async () => {
    mounted = await mount(MobileTopBar, { variant: 'top', title: 'Files' });
    const link = accountLink(mounted.host);
    expect(link?.getAttribute('aria-label')).toBe('Dev Admin, account settings');
    expect(link?.hasAttribute('aria-haspopup')).toBe(false);
    document.addEventListener('click', (event) => event.preventDefault(), { once: true });
    await mounted.click(link);
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(document.body.textContent).not.toContain('Log out');
  });

  it('leaves the avatar out of a detail view', async () => {
    mounted = await mount(MobileTopBar, { variant: 'detail', title: 'Thread' });
    expect(accountLink(mounted.host)).toBeNull();
  });
});
