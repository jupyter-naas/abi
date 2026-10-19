// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import { catalogsView, fakeApi, managedPolicy, readerPolicy } from '../access-fixtures';
import { PoliciesView } from './policies';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

async function open(can: (a: string) => boolean, over: Record<string, unknown> = {}) {
  const api = fakeApi({
    listPolicies: vi.fn().mockResolvedValue({ items: [managedPolicy, readerPolicy], next_after: null }),
    catalogs: vi.fn().mockResolvedValue(catalogsView),
    ...over,
  });
  mounted = await mount(PoliciesView, { api, can });
  await mounted.flush();
}

describe('PoliciesView', () => {
  it('lists policies and marks the managed ones', async () => {
    await open(() => true);
    const managed = document.querySelector('[data-policy="builtin.viewer"]');
    expect(managed?.textContent).toContain('managed');
    expect(document.querySelector('[data-policy="pol_1"]')?.textContent).toContain('Graph reader');
    expect(document.querySelector('[aria-label="Delete Viewer"]')).toBeNull();
    expect(document.querySelector('[aria-label="Delete Graph reader"]')).not.toBeNull();
  });

  it('opens a managed policy read-only', async () => {
    await open(() => true);
    await mounted!.click(document.querySelector('[data-policy="builtin.viewer"] button'));
    expect(mounted!.host.textContent).toContain('Managed: IAM writes this policy');
    expect(button('Save changes')).toBeUndefined();
  });

  it('asks before deleting, then deletes and reloads', async () => {
    const deletePolicy = vi.fn().mockResolvedValue(undefined);
    await open(() => true, { deletePolicy });
    await mounted!.click(document.querySelector('[aria-label="Delete Graph reader"]'));
    expect(deletePolicy).not.toHaveBeenCalled();
    await mounted!.click(button('Confirm delete') ?? null);
    expect(deletePolicy).toHaveBeenCalledWith('pol_1');
  });

  it('shows no create or delete to a caller who may not', async () => {
    await open((action) => action === 'iam:ListPolicies');
    expect(button('New policy')).toBeUndefined();
    expect(document.querySelector('[aria-label="Delete Graph reader"]')).toBeNull();
    await mounted!.click(document.querySelector('[data-policy="pol_1"] button'));
    expect(button('Save changes')).toBeUndefined();
    expect(mounted!.host.textContent).toContain('Read only');
  });

  it('says why the list could not load', async () => {
    await open(() => true, { listPolicies: vi.fn().mockRejectedValue(new Error('You do not have permission')) });
    expect(mounted!.host.textContent).toContain('You do not have permission');
  });
});
