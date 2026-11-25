// @vitest-environment jsdom
// Its own file: Radix menus in jsdom do not reopen after another test left a dialog behind.
import { afterEach, describe, expect, it } from 'vitest';
import { act, createElement } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { Menu } from './menu';

let mounted: Mounted | null = null;

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Menu', () => {
  it('announces a ticked row as a checked choice', async () => {
    mounted = await mount(
      () =>
        createElement(Menu, {
          label: 'View',
          testId: 'view',
          items: [
            { id: 'grid', label: 'Grid', checked: true },
            { id: 'list', label: 'List', checked: false },
          ],
        }),
      {}
    );
    await act(async () => {
      document
        .querySelector('[data-testid="view"]')
        ?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    });
    const choices = [...document.querySelectorAll('[role="menuitemcheckbox"]')];
    expect(choices.map((row) => [row.textContent, row.getAttribute('aria-checked')])).toEqual([
      ['Grid', 'true'],
      ['List', 'false'],
    ]);
  });
});
