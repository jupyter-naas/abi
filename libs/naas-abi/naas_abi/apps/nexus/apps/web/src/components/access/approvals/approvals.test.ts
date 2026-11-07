// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { allowAll, fakeApi, manifest } from '../service-fixtures';
import { ApprovalsView } from './approvals';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const buttonNamed = (label: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) ?? null;

function setup() {
  return fakeApi({
    listManifests: vi.fn(() => Promise.resolve({ items: [manifest()] })),
    approveManifest: vi.fn(() => Promise.resolve(manifest({ status: 'approved' }))),
    rejectManifest: vi.fn(() => Promise.resolve(manifest({ status: 'rejected' }))),
  });
}

describe('ApprovalsView', () => {
  it('lists pending manifests first, with what they ask for', async () => {
    const api = setup();
    mounted = await mount(ApprovalsView, { api, can: allowAll });
    await mounted.flush();
    expect(api.listManifests).toHaveBeenCalledWith('pending');
    const card = document.querySelector('[data-manifest]');
    expect(card?.textContent).toContain('module/acme/people');
    expect(card?.textContent).toContain('triple_store:Query');
    expect(card?.textContent).toContain('aaaaaaaaaaaa');
  });

  it('shows the actions a module declares, read-only', async () => {
    const declaring = manifest({
      catalog: {
        service: 'acme_reports',
        version: 1,
        resource_types: [{ name: 'report', id: 'path' }],
        actions: [{ name: 'ExportReport', level: 'read', resource_types: ['report'], description: 'Export one.' }],
      },
    });
    const api = fakeApi({ listManifests: vi.fn(() => Promise.resolve({ items: [declaring] })) });
    mounted = await mount(ApprovalsView, { api, can: allowAll });
    await mounted.flush();
    const declared = document.querySelector('[aria-label="Declared actions"]');
    expect(declared?.textContent).toContain('acme_reports:ExportReport');
    expect(declared?.textContent).toContain('approved as');
    expect(declared?.querySelector('input')).toBeNull();
  });

  it('approves as submitted without a document', async () => {
    const api = setup();
    mounted = await mount(ApprovalsView, { api, can: allowAll });
    await mounted.flush();
    await mounted.click(buttonNamed('Approve'));
    expect(api.approveManifest).toHaveBeenCalledWith('sa_mod', 'a'.repeat(64));
  });

  it('narrows to the checked actions and resources and leaves Deny alone', async () => {
    const api = setup();
    mounted = await mount(ApprovalsView, { api, can: allowAll });
    await mounted.flush();
    await mounted.click(buttonNamed('Narrow…'));
    await mounted.click(document.querySelector('input[aria-label="triple_store:ListGraphs"]'));
    await mounted.click(document.querySelector('input[aria-label="abi:triple_store:graph/b"]'));
    expect(document.querySelector('[role="status"]')?.textContent).toBe(
      '1 of 2 actions removed, 1 of 2 resources removed',
    );
    // Deny statements are not editable.
    expect(document.querySelector('input[aria-label="triple_store:DropGraph"]')).toBeNull();

    await mounted.click(buttonNamed('Approve narrowed'));
    expect(api.approveManifest).toHaveBeenCalledWith('sa_mod', 'a'.repeat(64), {
      document: {
        version: '2026-10-13',
        statements: [
          {
            effect: 'Allow',
            actions: ['triple_store:Query'],
            resources: ['abi:triple_store:graph/a'],
          },
          { effect: 'Deny', actions: ['triple_store:DropGraph'], resources: ['*'] },
        ],
      },
    });
  });

  it('cannot approve a selection that grants nothing', async () => {
    const api = setup();
    mounted = await mount(ApprovalsView, { api, can: allowAll });
    await mounted.flush();
    await mounted.click(buttonNamed('Narrow…'));
    await mounted.click(document.querySelector('input[aria-label="triple_store:Query"]'));
    await mounted.click(document.querySelector('input[aria-label="triple_store:ListGraphs"]'));
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('reject');
    expect((buttonNamed('Approve narrowed') as HTMLButtonElement).disabled).toBe(true);
  });

  it('rejects only with a reason', async () => {
    const api = setup();
    mounted = await mount(ApprovalsView, { api, can: allowAll });
    await mounted.flush();
    await mounted.click(buttonNamed('Reject…'));
    expect((buttonNamed('Reject manifest') as HTMLButtonElement).disabled).toBe(true);
    await mounted.type(document.querySelector('[aria-label="Reason"]'), 'too broad');
    await mounted.click(buttonNamed('Reject manifest'));
    expect(api.rejectManifest).toHaveBeenCalledWith('sa_mod', 'a'.repeat(64), { reason: 'too broad' });
  });

  it('shows no decision buttons without the rights', async () => {
    const api = setup();
    mounted = await mount(ApprovalsView, { api, can: () => false });
    await mounted.flush();
    expect(document.querySelector('[data-manifest]')).not.toBeNull();
    expect(buttonNamed('Approve')).toBeNull();
    expect(buttonNamed('Narrow…')).toBeNull();
    expect(buttonNamed('Reject…')).toBeNull();
  });

  it('offers a decision only on pending manifests', async () => {
    const api = fakeApi({
      listManifests: vi.fn(() => Promise.resolve({ items: [manifest({ status: 'approved' })] })),
    });
    mounted = await mount(ApprovalsView, { api, can: allowAll });
    await mounted.flush();
    expect(buttonNamed('Approve')).toBeNull();
  });
});
