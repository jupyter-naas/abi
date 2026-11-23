// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { CapabilityGroup } from '@/lib/people';
import { CapabilityGroupPicker } from './invite-policy-picker';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const runners: CapabilityGroup = {
  id: 'grp_runners',
  name: 'Workflow runners',
  description: 'Runs the workflows of their workspaces',
  owner_scope: 'abi:nexus:organization/acme',
  scope: 'organization',
};
const pilot: CapabilityGroup = { ...runners, id: 'grp_pilot', name: 'Pilot seat', description: null };

const offered = () => [...document.querySelectorAll('[data-capability]')].map((input) => input.getAttribute('data-capability'));
const box = (id: string) => document.querySelector(`[data-capability="${id}"]`);

async function render(
  load: ReturnType<typeof vi.fn>,
  props: { at?: { organizationId: string } | { workspaceId: string } | null; value?: string[] } = {}
) {
  const onChange = vi.fn();
  mounted = await mount(CapabilityGroupPicker, {
    at: props.at === undefined ? { workspaceId: 'ws-1' } : props.at,
    value: props.value ?? [],
    onChange,
    load,
  });
  await mounted.flush();
  return onChange;
}

describe('the capability groups a person is put in', () => {
  it('offers the groups listed where the person is added, never a policy', async () => {
    const load = vi.fn().mockResolvedValue([runners, pilot]);
    await render(load);
    expect(load).toHaveBeenCalledWith({ workspaceId: 'ws-1' });
    expect(offered()).toEqual(['grp_runners', 'grp_pilot']);
    expect(document.querySelector('[data-policy]')).toBeNull();
    expect(document.querySelector('[data-capability-groups] legend')?.textContent).toContain('Capability groups');
  });

  it('adds a picked group and drops an unpicked one', async () => {
    const onChange = await render(vi.fn().mockResolvedValue([runners, pilot]), { value: ['grp_runners'] });
    expect((box('grp_runners') as HTMLInputElement).checked).toBe(true);
    await mounted!.click(box('grp_pilot'));
    expect(onChange).toHaveBeenLastCalledWith(['grp_runners', 'grp_pilot']);
    await mounted!.click(box('grp_runners'));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it('shows nothing to someone who may not list them, or with none to offer', async () => {
    await render(vi.fn().mockRejectedValue(new Error('You do not have permission to do this.')));
    expect(document.querySelector('[data-capability-groups]')).toBeNull();
    await mounted!.unmount();

    await render(vi.fn().mockResolvedValue([]));
    expect(document.querySelector('[data-capability-groups]')).toBeNull();
    await mounted!.unmount();

    const load = vi.fn();
    await render(load, { at: null });
    expect(load).not.toHaveBeenCalled();
    expect(document.querySelector('[data-capability-groups]')).toBeNull();
  });
});
