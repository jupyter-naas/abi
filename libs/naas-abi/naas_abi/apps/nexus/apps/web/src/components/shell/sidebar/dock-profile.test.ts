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
vi.mock('@/hooks/use-avatar-settings-links', () => ({ useWarmAvatarSettingsLinks: () => undefined }));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { name: 'Dev Admin', email: 'admin@joe.com' } }),
}));

import { DockProfile } from './dock-profile';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

async function avatar(labeled: boolean): Promise<HTMLAnchorElement | null> {
  mounted = await mount(DockProfile, { labeled });
  await mounted.flush();
  return mounted.host.querySelector('a');
}

describe('the avatar at the bottom of the dock', () => {
  it('opens Settings on the Account tab, named for whose account it is', async () => {
    const link = await avatar(false);
    expect(link?.getAttribute('href')).toBe('/account/profile');
    expect(link?.getAttribute('aria-label')).toBe('Dev Admin, account settings');
  });

  it('opens no popup: no menu, no email, nothing but the link', async () => {
    const link = await avatar(true);
    expect(link?.hasAttribute('aria-haspopup')).toBe(false);
    expect(link?.hasAttribute('aria-expanded')).toBe(false);
    expect(link?.textContent).toBe('DDev Admin');
    document.addEventListener('click', (event) => event.preventDefault(), { once: true });
    await mounted?.click(link);
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(document.body.textContent).not.toContain('admin@joe.com');
  });
});
