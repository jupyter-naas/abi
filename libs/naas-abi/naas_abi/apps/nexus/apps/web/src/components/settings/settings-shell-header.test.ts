// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { escapeLeavesSettings, SettingsShellHeader } from './settings-shell-header';

vi.mock('./settings-scope-switcher', () => ({ SettingsScopeSwitcher: () => null }));

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
  async function header(onBack: () => void) {
    mounted = await mount(SettingsShellHeader, {
      scopeTitle: 'Platform Settings',
      showScopeSwitcher: false,
      onBack,
      backAriaLabel: 'Back to workspace',
    });
  }

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
