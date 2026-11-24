// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { readRoleOptions } from '@/lib/member-roles';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

import { WorkspaceCreateUserForm } from './workspace-create-user';

const OPTIONS = readRoleOptions({
  groups: [
    { kind: 'level', id: 'grp_m', name: 'Members', level: 'member' },
    { kind: 'level', id: 'grp_v', name: 'Viewers', level: 'viewer' },
    { kind: 'own', id: 'grp_w', name: 'ABI workspace' },
    { kind: 'admins', id: 'grp_wa', name: 'ABI admins' },
  ],
  policies: [{ kind: 'policy', id: 'pol_a', name: 'Alpha reports' }],
});
const CREATED = {
  user: { id: 'usr_new', email: 'zoe@example.com', name: 'Zoe', status: 'invited' as const },
  member: null,
  provider: null,
  emailSent: true,
  warning: null,
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function render(set = vi.fn(async () => ({}))) {
  const createInWorkspace = vi.fn(async () => CREATED);
  const onCreated = vi.fn();
  mounted = await mount(WorkspaceCreateUserForm, {
    workspaceId: 'ws-1',
    workspaceName: 'ABI',
    prefill: { email: 'zoe@example.com' },
    back: { href: '/workspace/ws-1/settings/users', label: 'Users' },
    onCreated,
    onCancel: vi.fn(),
    api: { createInWorkspace },
    rolesApi: { options: async () => OPTIONS, set },
  });
  await mounted.flush();
  return { createInWorkspace, set, onCreated };
}

const field = (name: string) => mounted!.host.querySelector<HTMLInputElement>(`[data-field="${name}"]`);

describe('Create user in a workspace', () => {
  it('asks for the email, the full name and the Role, a Member of the workspace to start with', async () => {
    await render();
    expect(field('email')?.value).toBe('zoe@example.com');
    expect(field('name')).not.toBeNull();
    const tags = [...mounted!.host.querySelectorAll('[data-role]')].map((t) => t.textContent);
    expect(tags).toEqual(['ABI workspace', 'Members']);
    expect(mounted!.host.textContent).not.toMatch(/Job title|Organization admin/);
  });

  it('creates them with the level and admin picked, then makes their Role the one picked', async () => {
    const { createInWorkspace, set, onCreated } = await render();
    await mounted!.type(field('name'), 'Zoe');
    await mounted!.select(mounted!.host.querySelector('[data-field="add-role"]'), 'admins:grp_wa');
    await mounted!.select(mounted!.host.querySelector('[data-field="add-role"]'), 'policy:pol_a');
    await mounted!.click(mounted!.host.querySelector('[data-action="create"]'));
    await mounted!.flush();
    expect(createInWorkspace).toHaveBeenCalledWith('ws-1', {
      email: 'zoe@example.com',
      name: 'Zoe',
      level: 'member',
      admin: true,
      capabilities: [],
    });
    expect(set).toHaveBeenCalledWith({ kind: 'workspace', id: 'ws-1' }, 'usr_new', { groups: ['grp_w', 'grp_m', 'grp_wa'], policies: ['pol_a'] });
    expect(onCreated).toHaveBeenCalledWith(CREATED, null);
  });

  it('creates nothing for a Role that would give nothing', async () => {
    const { createInWorkspace } = await render();
    await mounted!.click(mounted!.host.querySelector('[data-role="level"] button'));
    await mounted!.click(mounted!.host.querySelector('[data-action="create"]'));
    expect(createInWorkspace).not.toHaveBeenCalled();
    expect(mounted!.host.textContent).toMatch(/use nothing/);
  });

  it('says when they were created but their Role not all made', async () => {
    const { onCreated } = await render(vi.fn(async () => Promise.reject(new Error('You may not attach Alpha reports'))));
    await mounted!.click(mounted!.host.querySelector('[data-action="create"]'));
    await mounted!.flush();
    expect(onCreated.mock.calls[0][1]).toMatch(/not all made: You may not attach Alpha reports/);
  });
});
