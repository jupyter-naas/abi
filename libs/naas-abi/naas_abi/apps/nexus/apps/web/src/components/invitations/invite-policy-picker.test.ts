// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { InvitePolicyPicker } from './invite-policy-picker';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const member = { id: 'builtin.member', name: 'Member', description: '', managed: true };
const features = { id: 'pol_features', name: 'Features of member', description: 'chat, files', managed: false };
const graph = { id: 'pol_graph', name: 'Graph readers', description: '', managed: false, owner_scope: 'abi:acme:-' };

const offered = () => [...document.querySelectorAll('[data-policy]')].map((input) => input.getAttribute('data-policy'));
const box = (id: string) => document.querySelector(`[data-policy="${id}"]`);

async function render(attachable: ReturnType<typeof vi.fn>, props: { scope?: string | null; value?: string[] } = {}) {
  const onChange = vi.fn();
  mounted = await mount(InvitePolicyPicker, {
    scope: props.scope === undefined ? 'abi:acme:ws-1' : props.scope,
    value: props.value ?? [],
    onChange,
    api: { attachable },
  });
  await mounted.flush();
  return onChange;
}

describe('the policies an invitation carries', () => {
  it('offers what the inviter may attach at the scope, never a built-in role', async () => {
    const attachable = vi.fn().mockResolvedValue({ items: [member, features, graph] });
    await render(attachable);
    expect(attachable).toHaveBeenCalledWith('abi:acme:ws-1');
    expect(offered()).toEqual(['pol_features', 'pol_graph']);
  });

  it('adds a picked policy and drops an unpicked one', async () => {
    const attachable = vi.fn().mockResolvedValue({ items: [features, graph] });
    const onChange = await render(attachable, { value: ['pol_features'] });
    expect((box('pol_features') as HTMLInputElement).checked).toBe(true);
    await mounted!.click(box('pol_graph'));
    expect(onChange).toHaveBeenLastCalledWith(['pol_features', 'pol_graph']);
    await mounted!.click(box('pol_features'));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it('shows nothing to an inviter who may not list the policies, or with none to offer', async () => {
    await render(vi.fn().mockRejectedValue(new Error('You do not have permission to do this.')));
    expect(document.querySelector('[data-invite-policies]')).toBeNull();
    await mounted!.unmount();

    await render(vi.fn().mockResolvedValue({ items: [member] }));
    expect(document.querySelector('[data-invite-policies]')).toBeNull();
    await mounted!.unmount();

    const attachable = vi.fn();
    await render(attachable, { scope: null });
    expect(attachable).not.toHaveBeenCalled();
    expect(document.querySelector('[data-invite-policies]')).toBeNull();
  });

  it('says that what attaches at the organization reaches no workspace feature', async () => {
    const attachable = vi.fn().mockResolvedValue({ items: [graph] });
    await render(attachable, { scope: 'abi:acme:-' });
    expect(document.querySelector('[data-invite-policies-org]')).not.toBeNull();
    await mounted?.unmount();
    mounted = null;
    await render(vi.fn().mockResolvedValue({ items: [graph] }));
    expect(document.querySelector('[data-invite-policies-org]')).toBeNull();
  });
});
