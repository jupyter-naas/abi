// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement, useState } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { BulkAccessBar, SelectAllCell, SelectRowCell, bulkSkipped, useRowSelection } from './bulk-access';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

function Harness({ onApply }: { onApply: (level: string, keys: string[]) => void }) {
  const keys = ['a', 'b', 'c'];
  const selection = useRowSelection(keys);
  const [, force] = useState(0);
  return createElement(
    'div',
    null,
    createElement('table', null, createElement('thead', null, createElement('tr', null, createElement(SelectAllCell, { selection, keys, noun: 'features' })))),
    createElement(
      'table',
      null,
      createElement(
        'tbody',
        null,
        ...keys.map((key) => createElement('tr', { key }, createElement(SelectRowCell, { selection, rowKey: key, label: key }))),
      ),
    ),
    createElement(BulkAccessBar, {
      selection,
      noun: 'feature',
      levels: ['none', 'read', 'write', 'admin'],
      onApply: (level: string) => {
        onApply(level, [...selection.selected]);
        force((n) => n + 1);
      },
    }),
  );
}

const boxes = (m: Mounted) => [...m.host.querySelectorAll<HTMLInputElement>('tbody input[type="checkbox"]')];
const all = (m: Mounted) => m.host.querySelector<HTMLInputElement>('thead input[type="checkbox"]')!;

describe('batch changes of access', () => {
  it('selects rows one by one or all at once, and clears them', async () => {
    mounted = await mount(Harness, { onApply: vi.fn() });
    expect(mounted.host.querySelector('[data-bulk-bar]')).toBeNull();
    // The settings' square checkbox, in a centred select column (header and rows alike).
    expect(all(mounted).className).toContain('rounded-none');
    expect(all(mounted).closest('th')?.className).toContain('settings-select-cell');
    expect(boxes(mounted)[0].closest('td')?.className).toContain('settings-select-cell');
    await mounted.click(boxes(mounted)[1]);
    expect(mounted.host.querySelector('[data-bulk-bar]')?.textContent).toContain('1 feature selected');
    expect(all(mounted).indeterminate).toBe(true);
    await mounted.click(all(mounted));
    expect(boxes(mounted).every((b) => b.checked)).toBe(true);
    expect(mounted.host.querySelector('[data-bulk-bar]')?.textContent).toContain('3 features selected');
    await mounted.click(all(mounted));
    expect(boxes(mounted).some((b) => b.checked)).toBe(false);
  });

  it('asks in a modal before changing the access of every row selected', async () => {
    const onApply = vi.fn();
    mounted = await mount(Harness, { onApply });
    await mounted.click(all(mounted));
    await mounted.click(mounted.host.querySelector('[data-bulk-bar] [data-level="read"]'));
    const dialog = document.querySelector('[data-bulk-confirm]');
    expect(dialog?.textContent).toContain('Set access to Read for 3 features?');
    expect(onApply).not.toHaveBeenCalled();
    const confirm = [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find(
      (b) => b.textContent === 'Set to Read',
    )!;
    await mounted.click(confirm);
    expect(onApply).toHaveBeenCalledWith('read', ['a', 'b', 'c']);
    expect(document.querySelector('[data-bulk-confirm]')).toBeNull();
  });

  it('says which rows a level does not fit', () => {
    expect(bulkSkipped(3, 1, 'feature')).toBe('1 of the 3 features cannot take this level and stays as it is.');
    expect(bulkSkipped(3, 0, 'feature')).toBeNull();
  });
});
