// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { attachment, fakeApi } from '../access-fixtures';
import { AttachForm } from './attach-form';
import { scopeLabel } from './attachments-model';
import { AttachmentTable } from './attachments-table';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const field = (label: string) => document.querySelector(`[aria-label="${label}"]`);
const options = () => [...document.querySelectorAll('[aria-label="Policy to attach"] option')].map((o) => (o as HTMLOptionElement).value);
const reader = { id: 'pol_1', name: 'Graph reader', description: '', managed: false };
const viewer = { id: 'builtin.viewer', name: 'Viewer', description: '', managed: true };

function formApi(over: Record<string, unknown> = {}) {
  return fakeApi({
    attachable: vi.fn().mockResolvedValue({ items: [viewer, reader] }),
    attach: vi.fn().mockResolvedValue(attachment()),
    ...over,
  });
}

describe('scopeLabel', () => {
  it('puts scopes in words', () => {
    expect(scopeLabel(null)).toBe('Everywhere');
    expect(scopeLabel('abi:-:-')).toBe('Platform');
    expect(scopeLabel('abi:acme:-')).toBe('Organization acme');
    expect(scopeLabel('abi:acme:ws-1')).toBe('Workspace ws-1 of acme');
    expect(scopeLabel('abi:acme:*')).toBe('Every workspace of acme');
  });
});

describe('AttachForm', () => {
  const principals = [
    { id: 'usr_bob', label: 'Bob', kind: 'user' as const },
    { id: 'grp_1', label: 'Analysts', kind: 'group' as const },
  ];

  it('attaches a policy IAM lets the caller attach at the scope', async () => {
    const api = formApi();
    const onAttached = vi.fn();
    mounted = await mount(AttachForm, { api, scope: 'abi:acme:ws-1', principals, onAttached });
    await mounted.flush();
    expect(api.attachable).toHaveBeenCalledWith('abi:acme:ws-1');

    await mounted.type(field('Principal to attach to'), 'usr_bob');
    await mounted.click(button('Attach policy') ?? null);
    await mounted.flush();

    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'pol_1', principal_id: 'usr_bob', scope: 'abi:acme:ws-1' });
    expect(onAttached).toHaveBeenCalled();
  });

  it('offers a built-in role to a group, never to a person (their role is a membership)', async () => {
    mounted = await mount(AttachForm, { api: formApi(), scope: 'abi:acme:ws-1', principals, onAttached: vi.fn() });
    await mounted.flush();
    await mounted.type(field('Principal to attach to'), 'usr_bob');
    expect(options()).toEqual(['pol_1']);
    await mounted.type(field('Principal to attach to'), 'grp_1');
    expect(options()).toEqual(['builtin.viewer', 'pol_1']);
  });

  it('never offers what comes with a role, and tells a typed id’s kind by its prefix', async () => {
    const companion = { id: 'builtin.platform.member', name: 'Platform member', description: '', managed: true };
    const api = formApi({ attachable: vi.fn().mockResolvedValue({ items: [companion, viewer, reader] }) });
    mounted = await mount(AttachForm, { api, scope: 'abi:acme:ws-1', principals: [], onAttached: vi.fn() });
    await mounted.flush();
    await mounted.type(field('Principal to attach to'), 'usr_typed');
    expect(options()).toEqual(['pol_1']);
    await mounted.type(field('Principal to attach to'), 'grp_typed');
    expect(options()).toEqual(['builtin.viewer', 'pol_1']);
    await mounted.type(field('Principal to attach to'), 'sa_typed');
    expect(options()).toEqual(['builtin.viewer', 'pol_1']);
  });

  it('attaches to a fixed principal, platform-wide without a scope', async () => {
    const api = formApi();
    mounted = await mount(AttachForm, { api, scope: null, principals: [], principalId: 'grp_1', onAttached: vi.fn() });
    await mounted.flush();
    expect(field('Principal to attach to')).toBeNull();
    await mounted.click(button('Attach policy') ?? null);
    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'builtin.viewer', principal_id: 'grp_1', scope: null });
  });

  it('shows IAM’s refusal of an attach', async () => {
    const api = formApi({ attach: vi.fn().mockRejectedValue(new Error('You cannot grant what you do not hold: …')) });
    mounted = await mount(AttachForm, { api, scope: 'abi:acme:-', principals, onAttached: vi.fn() });
    await mounted.flush();
    await mounted.type(field('Principal to attach to'), 'grp_1');
    await mounted.click(button('Attach policy') ?? null);
    await mounted.flush();

    expect(document.querySelector('[role="alert"]')?.textContent).toContain('do not hold');
  });
});

describe('AttachmentTable', () => {
  it('detaches after a confirmation', async () => {
    const onDetach = vi.fn();
    mounted = await mount(AttachmentTable, { items: [attachment()], canDetach: true, onDetach });
    expect(document.querySelector('[data-attachment="att_1"]')?.textContent).toContain('Organization acme');
    await mounted.click(document.querySelector('[aria-label="Detach Graph reader from Ada"]'));
    expect(onDetach).not.toHaveBeenCalled();
    await mounted.click(button('Confirm detach') ?? null);
    expect(onDetach).toHaveBeenCalledWith(attachment());
  });

  it('shows no detach without the right', async () => {
    mounted = await mount(AttachmentTable, { items: [attachment()], canDetach: false, onDetach: vi.fn() });
    expect(button('Detach')).toBeUndefined();
  });
});
