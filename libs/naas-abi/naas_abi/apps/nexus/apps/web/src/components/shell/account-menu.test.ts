// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const session = vi.hoisted(() => ({ logout: vi.fn(), pushed: [] as string[] }));

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: (to: string) => session.pushed.push(to), replace: () => undefined }),
  usePathname: () => '/workspace/ws-joe/home',
}));
vi.mock('@/hooks/use-avatar-settings-links', () => ({
  useWarmAvatarSettingsLinks: () => undefined,
  useSettingsHref: () => '/workspace/ws-joe/settings/general',
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { name: 'Dev Admin', email: 'admin@joe.com' }, logout: session.logout }),
}));

import { useWorkspaceStore } from '@/stores/workspace';
import { AccountMenu, placeAccountMenu, type MenuAnchor } from './account-menu';

const joe = {
  id: 'ws-joe',
  name: 'JOE',
  organizationId: 'org-joe',
  organizationName: 'JOE Platform',
  currentUserRole: 'admin',
  theme: { primaryColor: '#22c55e' },
};
const other = {
  id: 'ws-other',
  name: 'Other',
  organizationId: 'org-other',
  organizationName: 'Other Org',
  currentUserRole: 'member',
  theme: { primaryColor: '#3b82f6' },
};

let mounted: Mounted | null = null;

beforeEach(() => {
  session.logout.mockClear();
  session.pushed = [];
  useWorkspaceStore.setState({
    workspaces: [joe, other] as never,
    currentWorkspaceId: 'ws-joe',
    activeConversationId: 'conv-keep',
    activePanelSection: null,
    panelSectionBeforeWorkspaces: null,
  });
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
  useWorkspaceStore.setState({
    workspaces: [],
    currentWorkspaceId: null,
    activeConversationId: null,
    activePanelSection: null,
    panelSectionBeforeWorkspaces: null,
  });
});

async function openMenu(): Promise<HTMLElement> {
  mounted = await mount(AccountMenu, { labeled: true });
  await mounted.flush();
  await mounted.click(mounted.host.querySelector('button'));
  const menu = document.querySelector<HTMLElement>('[role="menu"]');
  if (!menu) throw new Error('menu did not open');
  return menu;
}

function row(menu: ParentNode, id: string): HTMLElement {
  const found = menu.querySelector<HTMLElement>(`[data-account-row="${id}"]`);
  if (!found) throw new Error(`missing row ${id}`);
  return found;
}

const box = (partial: MenuAnchor): MenuAnchor => partial;

describe('the account menu', () => {
  it('lists name, workspace and role, Find workspace, Account, Settings, then Log out', async () => {
    const menu = await openMenu();
    expect([...menu.querySelectorAll('[data-account-row]')].map((el) => el.getAttribute('data-account-row'))).toEqual([
      'identity', 'workspace', 'find', 'account', 'settings', 'logout',
    ]);
    expect(row(menu, 'identity').querySelector('a')).toBeNull();
    expect(row(menu, 'identity').textContent).toContain('Dev Admin');
    expect(row(menu, 'identity').textContent).toContain('admin@joe.com');
    expect(row(menu, 'workspace').querySelector('a')).toBeNull();
    expect(row(menu, 'workspace').textContent?.trim()).toBe('JOE · Admin');
    expect(row(menu, 'find').textContent?.trim()).toBe('Find workspace');
    expect(row(menu, 'account').getAttribute('href')).toBe('/account/profile');
    expect(row(menu, 'account').textContent?.trim()).toBe('Account');
    expect(row(menu, 'settings').getAttribute('href')).toBe('/workspace/ws-joe/settings/general');
    expect(row(menu, 'settings').textContent?.trim()).toBe('Settings');
    expect(row(menu, 'logout').textContent?.trim()).toBe('Log out');
    expect(menu.textContent).not.toMatch(/Help|Download app|Upgrade|Usage|Language|API keys/);
  });

  it('opens the same Workspaces column as the workspace mark, and closes it the same way', async () => {
    const menu = await openMenu();
    await mounted?.click(row(menu, 'find'));
    expect(useWorkspaceStore.getState().activePanelSection).toBe('workspaces');
    expect(document.querySelector('[aria-label="Find workspace"]')).toBeNull();

    const again = await openMenu();
    await mounted?.click(row(again, 'find'));
    expect(useWorkspaceStore.getState().activePanelSection).toBeNull();
  });

  it('logs out through the existing logout, then the login page', async () => {
    const menu = await openMenu();
    await mounted?.click(row(menu, 'logout'));
    expect(session.logout).toHaveBeenCalledOnce();
    expect(session.pushed).toEqual(['/auth/login']);
  });
});

describe('placeAccountMenu', () => {
  it('opens upward at the width of a wide nav column', () => {
    const placed = placeAccountMenu(
      box({ top: 700, bottom: 748, left: 0, width: 280 }),
      box({ top: 0, bottom: 800, left: 0, width: 280 }),
      { width: 1200, height: 800 },
    );
    expect(placed.open).toBe('up');
    expect(placed.width).toBe(280);
    expect(placed.left).toBe(0);
    expect(placed.bottom).toBe(100);
  });

  it('stays readable above the icon rail, still growing upward from its left edge', () => {
    const placed = placeAccountMenu(
      box({ top: 720, bottom: 760, left: 8, width: 40 }),
      box({ top: 0, bottom: 800, left: 0, width: 56 }),
      { width: 1200, height: 800 },
    );
    expect(placed.open).toBe('up');
    expect(placed.left).toBe(0);
    expect(placed.width).toBe(256);
  });

  it('opens under a control that sits in the phone top bar, still on screen', () => {
    const placed = placeAccountMenu(
      box({ top: 8, bottom: 40, left: 340, width: 32 }),
      box({ top: 8, bottom: 40, left: 340, width: 32 }),
      { width: 390, height: 844 },
    );
    expect(placed.open).toBe('down');
    expect(placed.top).toBe(48);
    expect(placed.left + placed.width).toBeLessThanOrEqual(390 - 8);
  });
});
