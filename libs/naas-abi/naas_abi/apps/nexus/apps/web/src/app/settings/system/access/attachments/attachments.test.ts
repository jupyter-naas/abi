// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import { ada, attachment, ci, fakeApi } from '../access-fixtures';
import { scopeLabel } from './attachments-model';
import { AttachmentsPanel } from './attachments-panel';
import { AttachmentsView } from './attachments';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const field = (label: string) => document.querySelector(`[aria-label="${label}"]`);
const reader = { id: 'builtin.viewer', name: 'Viewer', description: '', managed: true };

function panelApi(over: Record<string, unknown> = {}) {
  return fakeApi({
    listAttachments: vi.fn().mockResolvedValue({ items: [attachment()] }),
    attachable: vi.fn().mockResolvedValue({ items: [reader] }),
    attach: vi.fn().mockResolvedValue(attachment()),
    detach: vi.fn().mockResolvedValue(undefined),
    ...over,
  });
}

const scopes = [
  { value: 'abi:acme:-', label: 'Organization' },
  { value: 'abi:acme:ws-1', label: 'Workspace ws-1' },
];

describe('scopeLabel', () => {
  it('puts scopes in words', () => {
    expect(scopeLabel(null)).toBe('Everywhere');
    expect(scopeLabel('abi:-:-')).toBe('Platform');
    expect(scopeLabel('abi:acme:-')).toBe('Organization acme');
    expect(scopeLabel('abi:acme:ws-1')).toBe('Workspace ws-1 of acme');
    expect(scopeLabel('abi:acme:*')).toBe('Every workspace of acme');
  });
});

describe('AttachmentsPanel', () => {
  it('lists what is attached at the scope, with who holds it', async () => {
    const api = panelApi();
    mounted = await mount(AttachmentsPanel, { api, scopes, can: () => true });
    await mounted.flush();

    expect(api.listAttachments).toHaveBeenCalledWith({ scope: 'abi:acme:-' });
    const row = document.querySelector('[data-attachment="att_1"]');
    expect(row?.textContent).toContain('Graph reader');
    expect(row?.textContent).toContain('Ada');
  });

  it('attaches a policy at the scope', async () => {
    const api = panelApi();
    mounted = await mount(AttachmentsPanel, { api, scopes, can: () => true, principals: [{ id: ci.id, label: 'ci' }] });
    await mounted.flush();
    expect(api.attachable).toHaveBeenCalledWith('abi:acme:-');

    await mounted.type(field('Principal to attach to'), 'usr_bob');
    await mounted.click(button('Attach policy') ?? null);
    await mounted.flush();

    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'builtin.viewer', principal_id: 'usr_bob', scope: 'abi:acme:-' });
    expect([...document.querySelectorAll('datalist option')].map((o) => (o as HTMLOptionElement).value)).toEqual([ci.id, ada.id]);
  });

  it('attaches at another scope after switching to it', async () => {
    const api = panelApi();
    mounted = await mount(AttachmentsPanel, { api, scopes, can: () => true });
    await mounted.flush();
    const select = field('Scope') as HTMLSelectElement;
    select.value = '1';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted.flush();
    await mounted.type(field('Principal to attach to'), 'usr_bob');
    await mounted.click(button('Attach policy') ?? null);

    expect(api.listAttachments).toHaveBeenLastCalledWith({ scope: 'abi:acme:ws-1' });
    expect(api.attach).toHaveBeenCalledWith(expect.objectContaining({ scope: 'abi:acme:ws-1' }));
  });

  it('detaches after a confirmation, at the attachment’s scope', async () => {
    const api = panelApi();
    mounted = await mount(AttachmentsPanel, { api, scopes, can: () => true });
    await mounted.flush();
    await mounted.click(document.querySelector('[aria-label="Detach Graph reader from Ada"]'));
    expect(api.detach).not.toHaveBeenCalled();
    await mounted.click(button('Confirm detach') ?? null);

    expect(api.detach).toHaveBeenCalledWith({ policy_id: 'pol_1', principal_id: ada.id, scope: 'abi:acme:-' });
  });

  it('shows IAM’s refusal of an attach', async () => {
    const api = panelApi({ attach: vi.fn().mockRejectedValue(new Error('You do not have permission to do this.')) });
    mounted = await mount(AttachmentsPanel, { api, scopes, can: () => true });
    await mounted.flush();
    await mounted.type(field('Principal to attach to'), 'usr_bob');
    await mounted.click(button('Attach policy') ?? null);
    await mounted.flush();

    expect(document.querySelector('[role="alert"]')?.textContent).toContain('do not have permission');
  });

  it('shows no attach form or detach button without the rights', async () => {
    const api = panelApi();
    mounted = await mount(AttachmentsPanel, { api, scopes, can: (a) => a === 'iam:ListAttachments' });
    await mounted.flush();

    expect(button('Attach policy')).toBeUndefined();
    expect(field('Principal to attach to')).toBeNull();
    expect(button('Detach')).toBeUndefined();
    expect(api.attachable).not.toHaveBeenCalled();
  });
});

describe('AttachmentsView', () => {
  it('filters, and attaches platform-wide with an empty scope', async () => {
    const api = panelApi({ listPrincipals: vi.fn().mockResolvedValue({ items: [ada], next_after: null }) });
    mounted = await mount(AttachmentsView, { api, can: () => true });
    await mounted.flush();
    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: undefined, policy_id: undefined, scope: undefined });
    expect(document.querySelector('[data-attachment="att_1"]')?.textContent).toContain('Organization acme');

    await mounted.type(field('Filter by principal id'), ada.id);
    await mounted.click(button('Apply') ?? null);
    await mounted.flush();
    expect(api.listAttachments).toHaveBeenLastCalledWith({ principal_id: ada.id, policy_id: undefined, scope: undefined });

    await mounted.type(field('Principal to attach to'), ada.id);
    await mounted.click(button('Attach policy') ?? null);
    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'builtin.viewer', principal_id: ada.id, scope: null });
  });

  it('attaches at the typed scope, offering the policies attachable there', async () => {
    const api = panelApi({ listPrincipals: vi.fn().mockResolvedValue({ items: [], next_after: null }) });
    mounted = await mount(AttachmentsView, { api, can: () => true });
    await mounted.flush();
    await mounted.type(field('Attach at scope'), 'abi:acme:ws-1');
    (field('Attach at scope') as HTMLInputElement).dispatchEvent(new FocusEvent('focusout', { bubbles: true }));
    await mounted.flush();
    expect(api.attachable).toHaveBeenLastCalledWith('abi:acme:ws-1');

    await mounted.type(field('Principal to attach to'), ada.id);
    await mounted.click(button('Attach policy') ?? null);
    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'builtin.viewer', principal_id: ada.id, scope: 'abi:acme:ws-1' });
  });

  it('hides attach and detach from someone who may only list', async () => {
    const api = panelApi();
    mounted = await mount(AttachmentsView, { api, can: (a) => a === 'iam:ListAttachments' });
    await mounted.flush();
    expect(button('Attach policy')).toBeUndefined();
    expect(button('Detach')).toBeUndefined();
  });
});
