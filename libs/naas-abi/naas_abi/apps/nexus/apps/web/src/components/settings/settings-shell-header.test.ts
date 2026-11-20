// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { SettingsTab } from './settings-levels';

const session = vi.hoisted(() => ({ logout: vi.fn(), pushed: [] as string[] }));

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: (to: string) => session.pushed.push(to) }) }));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) => select({ logout: session.logout }),
}));

import { FEATURE_KEYS, isWorkspacePathAllowed } from '@/lib/feature-access';
import { useWorkspaceStore } from '@/stores/workspace';
import { escapeLeavesSettings, SettingsShellHeader } from './settings-shell-header';

function escapeFrom(target: EventTarget): KeyboardEvent {
  const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
  target.dispatchEvent(event);
  return event;
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

describe('escapeLeavesSettings', () => {
  it('leaves on a plain Esc', () => {
    const event = new KeyboardEvent('keydown', { key: 'Escape' });
    expect(escapeLeavesSettings(event)).toBe(true);
  });

  it('stays on another key, or an Esc something already handled', () => {
    expect(escapeLeavesSettings(new KeyboardEvent('keydown', { key: 'Enter' }))).toBe(false);
    const handled = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true });
    handled.preventDefault();
    expect(escapeLeavesSettings(handled)).toBe(false);
  });

  it('stays while the caller types in a field', () => {
    for (const tag of ['input', 'textarea', 'select']) {
      const field = document.createElement(tag);
      document.body.append(field);
      let leaves: boolean | null = null;
      field.addEventListener('keydown', (event) => {
        leaves = escapeLeavesSettings(event as KeyboardEvent);
      });
      escapeFrom(field);
      expect(leaves, tag).toBe(false);
    }
  });

  it('stays while a menu, listbox or popover is open', () => {
    for (const html of [
      '<div role="menu"></div>',
      '<div role="listbox"></div>',
      '<div data-radix-popper-content-wrapper></div>',
      '<div role="dialog" data-state="open"></div>',
    ]) {
      document.body.innerHTML = html;
      expect(escapeLeavesSettings(new KeyboardEvent('keydown', { key: 'Escape' })), html).toBe(false);
    }
  });
});

describe('SettingsShellHeader', () => {
  async function header(onBack: () => void, props: { detailTitle?: string; tabs?: SettingsTab[] } = {}) {
    mounted = await mount(SettingsShellHeader, {
      ...props,
      onBack,
      backAriaLabel: 'Back to workspace',
    });
  }

  const TABS: SettingsTab[] = [
    { id: 'platform', label: 'Platform', href: '/settings/general', active: false },
    { id: 'organization', label: 'Organization · Acme', href: '/organizations/acme/settings/general', active: false },
    { id: 'workspace', label: 'Workspace', href: '/workspace/ws-1/settings/members', active: true },
    { id: 'account', label: 'Account', href: '/account/profile', active: false },
  ];

  it('reads Settings at every level, and the page on a phone', async () => {
    await header(() => undefined);
    expect(mounted?.host.querySelector('h1')?.textContent).toBe('Settings');
    await mounted?.unmount();
    await header(() => undefined, { detailTitle: 'Members' });
    expect(mounted?.host.querySelector('h1')?.textContent).toBe('Members');
  });

  it('has a tab per level under the title, the page\'s marked', async () => {
    await header(() => undefined, { tabs: TABS });
    expect(mounted?.host.querySelector('h1')?.textContent).toBe('Settings');
    const tabs = [...(mounted?.host.querySelectorAll<HTMLAnchorElement>('nav[aria-label="Settings levels"] a') ?? [])];
    expect(tabs.map((tab) => [tab.textContent, tab.getAttribute('href')])).toEqual(TABS.map((tab) => [tab.label, tab.href]));
    const current = tabs.filter((tab) => tab.getAttribute('aria-current') === 'true').map((tab) => tab.textContent);
    expect(current).toEqual(['Workspace']);
  });

  it('has Help and Log out at the right of the bar, at every level and on a phone\'s page', async () => {
    useWorkspaceStore.setState({ currentWorkspaceId: 'ws-1' });
    const levels: { tabs?: SettingsTab[]; detailTitle?: string }[] = [
      ...TABS.map((active) => ({ tabs: TABS.map((tab) => ({ ...tab, active: tab.id === active.id })) })),
      { tabs: [] },
      { detailTitle: 'Members' },
    ];
    for (const props of levels) {
      await header(() => undefined, props);
      const actions = mounted?.host.querySelector('header .settings-header-actions');
      expect(actions?.querySelector('a[aria-label="Help"]')?.getAttribute('href')).toBe('/workspace/ws-1/help');
      expect(actions?.querySelector('button[aria-label="Log out"]')).not.toBeNull();
      await mounted?.unmount();
      mounted = null;
    }
  });

  it('has Help for a member holding only chat and files, and Help opens for them', async () => {
    useWorkspaceStore.setState({ currentWorkspaceId: 'ws-1' });
    await header(() => undefined);
    const href = mounted?.host.querySelector('a[aria-label="Help"]')?.getAttribute('href') ?? '';
    expect(href).toBe('/workspace/ws-1/help');
    const workspaceFlags = Object.fromEntries(
      FEATURE_KEYS.map((feature) => [feature, feature === 'chat' || feature === 'files']),
    );
    expect(isWorkspacePathAllowed({ pathname: href, role: 'member', workspaceFlags })).toBe(true);
  });

  it('logs out as the session always did, then goes to the sign-in page', async () => {
    session.logout.mockClear();
    session.pushed = [];
    await header(() => undefined, { tabs: TABS });
    await mounted?.click(mounted.host.querySelector('button[aria-label="Log out"]'));
    expect(session.logout).toHaveBeenCalledTimes(1);
    expect(session.pushed).toEqual(['/auth/login']);
  });

  it('has no tab bar without tabs (one level, or a page on a phone)', async () => {
    await header(() => undefined, { tabs: [] });
    expect(mounted?.host.querySelector('nav')).toBeNull();
    await mounted?.unmount();
    await header(() => undefined, { detailTitle: 'Members' });
    expect(mounted?.host.querySelector('nav')).toBeNull();
  });

  it('goes back on Esc', async () => {
    const onBack = vi.fn();
    await header(onBack);
    escapeFrom(document.body);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('does not go back on Esc in a search box', async () => {
    const onBack = vi.fn();
    await header(onBack);
    const search = document.createElement('input');
    search.type = 'search';
    document.body.append(search);
    escapeFrom(search);
    expect(onBack).not.toHaveBeenCalled();
  });
});
