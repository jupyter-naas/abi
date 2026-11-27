// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, createElement, Fragment } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { useConfirm } from './dialogs';
import { Menu } from './menu';
import { Tabs } from './tabs';

let mounted: Mounted | null = null;

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
  vi.useRealTimers();
});

async function open(trigger: Element | null) {
  await act(async () => {
    trigger?.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true }));
  });
}

function EditMenu() {
  const { confirm, dialog } = useConfirm();
  return createElement(
    Fragment,
    null,
    createElement(Menu, {
      label: 'Edit',
      testId: 'edit',
      items: [
        { id: 'delete', label: 'Delete page', testId: 'delete', onSelect: () => void confirm({ title: 'Delete the page?' }) },
        { id: 'grid', label: 'Grid', checked: true },
        { id: 'list', label: 'List', checked: false },
      ],
    }),
    dialog
  );
}

describe('Menu', () => {
  it('leaves focus in a dialog an item opened, not on the trigger', async () => {
    mounted = await mount(EditMenu, {});
    await open(document.querySelector('[data-testid="edit"]'));
    await mounted.click(document.querySelector('[data-testid="delete"]'));
    // Radix restores focus to the trigger in a timeout after the menu closes.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.contains(document.activeElement)).toBe(true);
    await mounted.click([...(dialog?.querySelectorAll('button') ?? [])].find((b) => b.textContent === 'Cancel') ?? null);
  });});

describe('Tabs', () => {
  it('keeps one tab in the keyboard order when none is selected', async () => {
    mounted = await mount(
      () =>
        createElement(Tabs<string>, {
          label: 'View',
          value: '',
          onChange: () => undefined,
          items: [
            { id: 'jobs', label: 'Jobs' },
            { id: 'runs', label: 'Runs' },
          ],
        }),
      {}
    );
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    expect(tabs.map((tab) => tab.getAttribute('tabindex'))).toEqual(['0', '-1']);
  });
});
