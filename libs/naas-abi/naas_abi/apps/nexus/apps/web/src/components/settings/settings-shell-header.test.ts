// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { SettingsTab } from './settings-levels';

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});

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
