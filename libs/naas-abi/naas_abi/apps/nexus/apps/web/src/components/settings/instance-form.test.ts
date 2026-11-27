// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { FormSaveButton, UnsavedBar } from './instance-form';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const button = () => mounted!.host.querySelector('[data-action="save"]') as HTMLButtonElement;

describe('the form parts of an instance page', () => {
  it('fades Save until something changes', async () => {
    mounted = await mount(FormSaveButton, { dirty: false, saving: false, onSave: vi.fn() });
    expect(button().disabled).toBe(true);
    expect(button().className).toContain('org-settings-primary-button');
  });

  it('saves once something changed, and says Saved! after', async () => {
    const onSave = vi.fn();
    mounted = await mount(FormSaveButton, { dirty: true, saving: false, onSave });
    await mounted.click(button());
    expect(onSave).toHaveBeenCalledTimes(1);
    await mounted.unmount();
    mounted = await mount(FormSaveButton, { dirty: false, saving: false, saved: true, onSave });
    expect(button().textContent).toBe('Saved!');
  });

  it('says there are unsaved changes, or what changed elsewhere, and discards them', async () => {
    const onDiscard = vi.fn();
    mounted = await mount(UnsavedBar, { show: true, onDiscard, conflicts: ['Name'] });
    expect(mounted.host.textContent).toContain('Changed elsewhere since you began editing: Name.');
    await mounted.click(mounted.host.querySelector('[data-action="discard"]'));
    expect(onDiscard).toHaveBeenCalled();
    await mounted.unmount();
    mounted = await mount(UnsavedBar, { show: false, onDiscard });
    expect(mounted.host.querySelector('[data-unsaved-bar]')).toBeNull();
  });
});
