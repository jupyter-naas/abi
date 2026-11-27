// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement, useState } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { BulkAccessBar, BulkBar, SelectAllCell, SelectRowCell, bulkSkipped, onOffActions, useRowSelection } from './bulk-access';

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
    expect(bulkSkipped(2, 1, 'skill', 'this change')).toBe('1 of the 2 skills cannot take this change and stays as it is.');
  });

  it('switches the selected rows of an on/off column on or off, asked first, in the words of the page', async () => {
    const actions = onOffActions({ on: 'Enable', off: 'Disable' });
    expect(actions.map((a) => [a.id, a.label, a.confirm])).toEqual([
      ['on', 'Enable', 'Enable'],
      ['off', 'Disable', 'Disable'],
    ]);
    expect(actions[1].question(2, 'skills')).toBe('Disable 2 skills?');

    const applied: string[] = [];
    function OnOff() {
      const selection = useRowSelection(['a', 'b']);
      return createElement(
        'div',
        null,
        createElement('table', null, createElement('tbody', null, createElement('tr', null, createElement(SelectRowCell, { selection, rowKey: 'a', label: 'a' }), createElement(SelectRowCell, { selection, rowKey: 'b', label: 'b' })))),
        createElement(BulkBar, {
          selection,
          noun: 'skill',
          actions,
          onApply: (id: string) => {
            applied.push(id);
          },
          skippedFor: () => 1,
          change: 'this change',
        }),
      );
    }
    mounted = await mount(OnOff, {});
    await mounted.click(mounted.host.querySelector('[data-select-row="a"]'));
    await mounted.click(mounted.host.querySelector('[data-select-row="b"]'));
    await mounted.click(mounted.host.querySelector('[data-bulk-action="off"]'));
    const dialog = document.querySelector('[data-bulk-confirm]');
    expect(dialog?.textContent).toContain('Disable 2 skills?');
    expect(dialog?.textContent).toContain('1 of the 2 skills cannot take this change');
    const confirm = [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find((b) => b.textContent === 'Disable')!;
    await mounted.click(confirm);
    await mounted.flush();
    expect(applied).toEqual(['off']);
    expect(mounted.host.querySelector('[data-bulk-bar]')).toBeNull();
  });
});
