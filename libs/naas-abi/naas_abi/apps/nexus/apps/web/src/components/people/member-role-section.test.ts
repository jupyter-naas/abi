// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { HeldRoles, MemberRolesApi, RoleOptions, RoleSelection } from '@/lib/member-roles';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

import { MemberRoleSection } from './member-role-section';

const OPTIONS: RoleOptions = {
  groups: [
    { kind: 'level', id: 'grp_members', name: 'Members', level: 'member' },
    { kind: 'level', id: 'grp_viewers', name: 'Viewers', level: 'viewer' },
    { kind: 'own', id: 'grp_alpha', name: 'Alpha workspace' },
    { kind: 'admins', id: 'grp_alpha_admins', name: 'Alpha admins' },
    { kind: 'group', id: 'grp_runners', name: 'Workflow runners' },
    { kind: 'group', id: 'grp_auditors', name: 'Auditors' },
  ],
  policies: [
    { kind: 'policy', id: 'pol_read', name: 'Read reports' },
    { kind: 'policy', id: 'pol_export', name: 'Export data' },
  ],
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

function fakeApi(start: RoleSelection, names: Record<string, string> = {}, shown: HeldRoles['shown'] = []) {
  let held: HeldRoles = { ...start, names, shown };
  const set = vi.fn(async (_scope: unknown, _user: string, next: RoleSelection) => {
    held = { ...next, names, shown };
    return {};
  });
  const api: MemberRolesApi = {
    options: vi.fn(async () => OPTIONS),
    member: vi.fn(async () => ({ userId: 'usr_bob', name: 'Bob', email: 'bob@example.test', source: 'workspace' as const })),
    held: vi.fn(async () => held),
    set,
  };
  return { api, set };
}

async function render(start: RoleSelection, names: Record<string, string> = {}, shown: HeldRoles['shown'] = []) {
  const { api, set } = fakeApi(start, names, shown);
  const onPerson = vi.fn();
  mounted = await mount(MemberRoleSection, {
    scope: { kind: 'workspace', id: 'ws-alpha' },
    principalId: 'usr_iam_bob',
    onPerson,
    api,
  });
  await mounted.flush();
  return { set, onPerson };
}

const list = (kind: 'workspaces' | 'groups' | 'policies') =>
  [...document.body.querySelectorAll(`[data-role-list="${kind}"] [data-role-item]`)].map((li) => li.getAttribute('data-role-item'));
const dialog = () => document.body.querySelector<HTMLElement>('[data-role-picker]');
const confirmButton = (label: string) =>
  [...document.body.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) ?? null;

describe('A person’s Groups and Policies', () => {
  it('lists what they hold, each named, the workspace’s own group kept', async () => {
    const { onPerson } = await render(
      { groups: ['grp_runners', 'grp_members', 'grp_alpha', 'grp_hidden'], policies: ['pol_read'] },
      { grp_hidden: 'A group you are not offered' },
    );
    expect(onPerson).toHaveBeenCalledWith({ userId: 'usr_bob', name: 'Bob', email: 'bob@example.test', reachesOtherwise: false });
    expect(list('groups')).toEqual(['grp_alpha', 'grp_members', 'grp_hidden', 'grp_runners']);
    expect(document.body.querySelector('[data-role-item="grp_hidden"]')?.textContent).toContain('A group you are not offered');
    expect(document.body.querySelector('[data-role-item="grp_alpha"] [data-action="remove-role"]')).toBeNull();
    expect(list('policies')).toEqual(['pol_read']);
  });

  it('takes them out of the workspace from their membership row, once confirmed', async () => {
    const { api } = fakeApi({ groups: ['grp_alpha', 'grp_members'], policies: [] });
    const onLeave = vi.fn(() => Promise.resolve());
    mounted = await mount(MemberRoleSection, {
      scope: { kind: 'workspace', id: 'ws-alpha' },
      principalId: 'usr_iam_bob',
      api,
      onLeave,
    });
    await mounted.flush();
    const leave = document.body.querySelector('[data-role-item="grp_alpha"] [data-action="remove-from-workspace"]');
    expect(leave?.textContent).toContain('Remove from workspace');
    await mounted.click(leave);
    // Asked first, saying what they lose: nothing happens before the answer.
    expect(onLeave).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain('Remove Bob from this workspace?');
    await mounted.click(confirmButton('Cancel'));
    expect(onLeave).not.toHaveBeenCalled();
    await mounted.click(leave);
    // The modal's button (the row's carries the same words).
    const inModal = [...document.body.querySelectorAll('button')].filter((b) => b.textContent?.trim() === 'Remove from workspace').at(-1);
    await mounted.click(inModal!);
    await mounted.flush();
    expect(onLeave).toHaveBeenCalledTimes(1);
  });

  it('keeps the membership row without a way out when the page offers none', async () => {
    await render({ groups: ['grp_alpha'], policies: [] });
    expect(document.body.querySelector('[data-role-item="grp_alpha"] [data-action="remove-from-workspace"]')).toBeNull();
    expect(document.body.querySelector('[data-role-item="grp_alpha"]')?.textContent).toContain('Kept while they are here');
  });

  it('shows an organization admin’s groups managed elsewhere, none removable here', async () => {
    await render({ groups: ['grp_members'], policies: [] }, {}, [
      { id: 'grp_alpha', name: 'Alpha workspace', implied: true, managed: 'admins' },
      { id: 'grp_acme_admins', name: 'Acme admins', implied: false, managed: 'organization' },
    ]);
    expect(list('groups')).toEqual(['grp_alpha', 'grp_acme_admins', 'grp_members']);
    const managed = (id: string) => document.body.querySelector(`[data-role-item="${id}"] [data-managed]`)?.textContent;
    expect(managed('grp_alpha')).toBe('Comes with their admins group');
    expect(managed('grp_acme_admins')).toBe("Managed in the organization's Users");
    expect(document.body.querySelector('[data-role-item="grp_acme_admins"] [data-action="remove-role"]')).toBeNull();
    expect(document.body.querySelector('[data-role-item="grp_members"] [data-action="remove-role"]')).not.toBeNull();
  });

  it('lists an organization’s workspaces apart, added from their own search', async () => {
    const workspaceOptions: RoleOptions = {
      groups: [
        ...OPTIONS.groups,
        { kind: 'group', id: 'grp_sales', name: 'Sales workspace', workspace: 'ws-sales' },
        { kind: 'group', id: 'grp_sales_a', name: 'Sales admins', workspace: 'ws-sales', administers: true },
        { kind: 'group', id: 'grp_finance', name: 'Finance workspace', workspace: 'ws-finance' },
      ],
      policies: OPTIONS.policies,
    };
    const { api, set } = fakeApi({ groups: ['grp_members', 'grp_sales', 'grp_runners'], policies: [] });
    api.options = vi.fn(async () => workspaceOptions);
    mounted = await mount(MemberRoleSection, { scope: { kind: 'organization', id: 'org-1' }, userId: 'usr_bob', api });
    await mounted.flush();
    expect(list('workspaces')).toEqual(['grp_sales']);
    expect(document.body.querySelector('[data-role-item="grp_sales"]')?.textContent).toContain('Works in this workspace');
    expect(list('groups')).toEqual(['grp_members', 'grp_runners']);
    await mounted.click(document.body.querySelector('[data-action="add-workspaces"]'));
    const offered = [...dialog()!.querySelectorAll('[data-role-option]')].map((li) => li.getAttribute('data-role-option'));
    expect(offered).toEqual(['grp_sales_a', 'grp_finance']);
    await mounted.click(dialog()!.querySelector('[data-role-option="grp_finance"] input'));
    await mounted.click(dialog()!.querySelector('[data-action="add-picked"]'));
    await mounted.flush();
    expect(set.mock.calls[0][2].groups).toEqual(['grp_members', 'grp_sales', 'grp_runners', 'grp_finance']);
    expect(list('workspaces')).toEqual(['grp_finance', 'grp_sales']);
  });

  it('removes a group once confirmed, and nothing when cancelled', async () => {
    const { set } = await render({ groups: ['grp_alpha', 'grp_members', 'grp_runners'], policies: [] });
    await mounted!.click(document.body.querySelector('[data-role-item="grp_runners"] [data-action="remove-role"]'));
    expect(document.body.textContent).toContain('Remove from Workflow runners?');
    await mounted!.click(confirmButton('Cancel'));
    expect(set).not.toHaveBeenCalled();
    await mounted!.click(document.body.querySelector('[data-role-item="grp_runners"] [data-action="remove-role"]'));
    await mounted!.click(confirmButton('Remove'));
    await mounted!.flush();
    expect(set).toHaveBeenCalledWith({ kind: 'workspace', id: 'ws-alpha' }, 'usr_bob', {
      groups: ['grp_alpha', 'grp_members'],
      policies: [],
    });
    expect(list('groups')).toEqual(['grp_alpha', 'grp_members']);
  });

  it('says why a removal is refused, without asking', async () => {
    const { set } = await render({ groups: ['grp_alpha', 'grp_members'], policies: [] });
    await mounted!.click(document.body.querySelector('[data-role-item="grp_members"] [data-action="remove-role"]'));
    expect(document.body.textContent).toContain('They would use nothing here');
    expect(confirmButton('Remove')).toBeNull();
    expect(set).not.toHaveBeenCalled();
  });

  it('adds several groups picked in the search dialog', async () => {
    const { set } = await render({ groups: ['grp_alpha', 'grp_members'], policies: [] });
    // A text button, as every section's "+ …": not an icon alone.
    expect(document.body.querySelector('[data-action="add-groups"]')?.textContent).toBe('Add groups');
    expect(document.body.querySelector('[data-action="add-policies"]')?.textContent).toBe('Add policies');
    await mounted!.click(document.body.querySelector('[data-action="add-groups"]'));
    expect(dialog()).not.toBeNull();
    const offered = () => [...dialog()!.querySelectorAll('[data-role-option]')].map((li) => li.getAttribute('data-role-option'));
    expect(offered()).toEqual(['grp_viewers', 'grp_alpha_admins', 'grp_runners', 'grp_auditors']);
    await mounted!.type(dialog()!.querySelector('[data-field="role-search"]'), 'run');
    expect(offered()).toEqual(['grp_runners']);
    await mounted!.click(dialog()!.querySelector('[data-role-option="grp_runners"] input'));
    await mounted!.type(dialog()!.querySelector('[data-field="role-search"]'), '');
    await mounted!.click(dialog()!.querySelector('[data-role-option="grp_auditors"] input'));
    expect(dialog()!.querySelector('[data-action="add-picked"]')?.textContent).toBe('Add 2');
    await mounted!.click(dialog()!.querySelector('[data-action="add-picked"]'));
    await mounted!.flush();
    expect(set.mock.calls[0][2].groups).toEqual(['grp_alpha', 'grp_members', 'grp_runners', 'grp_auditors']);
    expect(dialog()).toBeNull();
  });

  it('replaces their level with the one picked, and refuses a Viewer admin', async () => {
    const { set } = await render({ groups: ['grp_alpha', 'grp_members', 'grp_alpha_admins'], policies: [] });
    await mounted!.click(document.body.querySelector('[data-action="add-groups"]'));
    await mounted!.click(dialog()!.querySelector('[data-role-option="grp_viewers"] input'));
    expect(dialog()!.querySelector('[data-role-problem]')?.textContent).toContain('a Viewer administers nothing');
    expect(dialog()!.querySelector<HTMLButtonElement>('[data-action="add-picked"]')!.disabled).toBe(true);
    expect(set).not.toHaveBeenCalled();
  });

  it('attaches a policy picked in the dialog', async () => {
    const { set } = await render({ groups: ['grp_alpha', 'grp_members'], policies: [] });
    await mounted!.click(document.body.querySelector('[data-action="add-policies"]'));
    await mounted!.click(dialog()!.querySelector('[data-role-option="pol_export"] input'));
    await mounted!.click(dialog()!.querySelector('[data-action="add-picked"]'));
    await mounted!.flush();
    expect(set.mock.calls[0][2].policies).toEqual(['pol_export']);
    expect(list('policies')).toEqual(['pol_export']);
  });
});
