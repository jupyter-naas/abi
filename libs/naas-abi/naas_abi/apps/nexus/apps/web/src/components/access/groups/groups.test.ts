// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { InviteProviders } from '@/lib/invitations';
import { mount, type Mounted } from '@/lib/testing/mount';
import { EMPTY_DIRECTORY } from '../access-directory';
import { PLATFORM_ACCESS_SCOPE } from '../access-scope';
import { attachment, fakeDirectory, member, wsScope } from '../access-fixtures';
import { allowAll, fakeApi, group, principal } from '../service-fixtures';
import { GroupsView } from './groups';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const buttonNamed = (label: string) =>
  [...document.querySelectorAll('button')].find(
    (b) => b.textContent?.trim() === label || b.getAttribute('aria-label') === label,
  ) ?? null;

const providers: InviteProviders = {
  enabled: true,
  default_provider: 'okta',
  providers: [{ name: 'okta', display_name: 'Okta', provisioning: 'none', managed_in_provider: true }],
};

function setup() {
  const detail = group({ members: [principal({ id: 'usr_9', display_name: 'Bob' })] });
  return fakeApi({
    listGroups: vi.fn(() => Promise.resolve({ items: [{ ...detail, member_count: 1 }], next_after: null })),
    getGroup: vi.fn(() => Promise.resolve(detail)),
    listPrincipals: vi.fn(() => Promise.resolve({ items: [principal()], next_after: null })),
    addMember: vi.fn(() => Promise.resolve(detail)),
    removeMember: vi.fn(() => Promise.resolve(detail)),
    mapIdpGroup: vi.fn(() => Promise.resolve(detail)),
    unmapIdpGroup: vi.fn(() => Promise.resolve(detail)),
    listAttachments: vi.fn(() => Promise.resolve({ items: [] })),
    attachable: vi.fn(() => Promise.resolve({ items: [] })),
  });
}

const platform = { scope: PLATFORM_ACCESS_SCOPE, directory: EMPTY_DIRECTORY };

async function open(api: ReturnType<typeof setup>, can: (a: string) => boolean = allowAll) {
  mounted = await mount(GroupsView, { api, can, ...platform, loadProviders: () => Promise.resolve(providers) });
  await mounted.flush();
  await mounted.click(document.querySelector('[data-group] button[data-action="open"]'));
  await mounted.flush();
}

describe('GroupsView', () => {
  it('lists groups with their member count, read with the list: no detail per group', async () => {
    const api = setup();
    mounted = await mount(GroupsView, { api, can: allowAll, ...platform, loadProviders: () => Promise.resolve(providers) });
    await mounted.flush();
    const row = document.querySelector('[data-group="grp_1"]');
    expect(row?.textContent).toContain('Analysts');
    expect(row?.textContent).toContain('Platform');
    expect(row?.querySelector('[data-field="members"]')?.textContent).toBe('1');
    expect(api.listGroups).toHaveBeenCalledTimes(1);
    expect(api.listGroups).toHaveBeenCalledWith(undefined, { after: null, limit: 500, memberCounts: true });
    expect(api.getGroup).not.toHaveBeenCalled();
  });

  it('shows no count for a group the caller may list but not read', async () => {
    const api = setup();
    (api as unknown as Record<string, unknown>).listGroups = vi.fn(() =>
      Promise.resolve({ items: [group({ member_count: null })], next_after: null }),
    );
    mounted = await mount(GroupsView, { api, can: allowAll, ...platform, loadProviders: () => Promise.resolve(providers) });
    await mounted.flush();
    expect(document.querySelector('[data-group="grp_1"] [data-field="members"]')?.textContent).toBe('–');
    expect(api.getGroup).not.toHaveBeenCalled();
  });

  it('adds a member picked in the search, name and email shown', async () => {
    const api = setup();
    await open(api);
    await mounted!.click(document.querySelector('[data-action="add-members"]'));
    const ada = document.querySelector('[data-attach-option="usr_1"]');
    expect(ada?.textContent).toContain('Ada');
    expect(ada?.textContent).toContain('ada@example.com');
    await mounted!.click(ada!.querySelector('button'));
    await mounted!.flush();
    expect(api.addMember).toHaveBeenCalledWith('grp_1', 'usr_1');
    expect(document.querySelector('[data-attach-dialog]')).toBeNull();
  });

  it('removes a member once confirmed', async () => {
    const api = setup();
    await open(api);
    await mounted!.click(buttonNamed('Remove Bob'));
    expect(api.removeMember).not.toHaveBeenCalled();
    await mounted!.click(buttonNamed('Confirm remove'));
    await mounted!.flush();
    expect(api.removeMember).toHaveBeenCalledWith('grp_1', 'usr_9');
  });

  it('maps an IdP group claim from a provider', async () => {
    const api = setup();
    await open(api);
    await mounted!.type(document.querySelector('[aria-label="Group claim value"]'), 'eng-admins');
    await mounted!.click(buttonNamed('Map group'));
    expect(api.mapIdpGroup).toHaveBeenCalledWith('grp_1', { provider: 'okta', claim_value: 'eng-admins' });
  });

  it('shows no write controls without the rights', async () => {
    const api = setup();
    await open(api, () => false);
    expect(document.querySelector('[data-action="add-members"]')).toBeNull();
    expect(buttonNamed('Map group')).toBeNull();
    expect(buttonNamed('Remove Bob')).toBeNull();
    expect(buttonNamed('Create group')).toBeNull();
    expect(buttonNamed('Delete Analysts')).toBeNull();
  });
});

describe('GroupsView at a workspace', () => {
  const owned = group({ id: 'grp_ws', name: 'Recruiters', owner_scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1', members: [] });
  const fromOrg = group({ id: 'grp_org', name: 'Org analysts', owner_scope: 'abi:nexus:organization/acme', members: [] });

  function workspaceApi(over: Record<string, unknown> = {}) {
    return fakeApi({
      listGroups: vi.fn(() => Promise.resolve({ items: [owned, fromOrg] })),
      getGroup: vi.fn((id: string) => Promise.resolve(id === owned.id ? owned : fromOrg)),
      createGroup: vi.fn(() => Promise.resolve(owned)),
      addMember: vi.fn(() => Promise.resolve(owned)),
      listAttachments: vi.fn(() => Promise.resolve({ items: [attachment({ principal_id: owned.id, scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' })] })),
      attachable: vi.fn(() =>
        Promise.resolve({
          items: [
            { id: 'pol_1', name: 'Graph reader', description: '', managed: false },
            { id: 'pol_2', name: 'Writer', description: '', managed: false },
          ],
        })
      ),
      attach: vi.fn(() => Promise.resolve(attachment())),
      ...over,
    });
  }
  // A workspace admin: the IdP mapping actions are the platform's, so `access` says no.
  const admin = (action: string) => !['iam:MapIdpGroup', 'iam:UnmapIdpGroup', 'iam:ListPrincipals'].includes(action);

  async function show(api: ReturnType<typeof workspaceApi>, groupId: string) {
    mounted = await mount(GroupsView, { api, can: admin, scope: wsScope, directory: fakeDirectory([member()]) });
    await mounted.flush();
    await mounted.click(document.querySelector(`[data-group="${groupId}"] button[data-action="open"]`));
    await mounted.flush();
  }

  it('creates a group owned by the workspace', async () => {
    const api = workspaceApi();
    mounted = await mount(GroupsView, { api, can: admin, scope: wsScope, directory: fakeDirectory([member()]) });
    await mounted.flush();
    expect(api.listGroups).toHaveBeenCalledWith('abi:nexus:organization/acme/nexus:workspace/ws-1', {
      after: null,
      limit: 500,
      memberCounts: true,
    });
    // Create group opens the page of a group to be, its sections already there: what it grants
    // (its policies), then who holds it (its members), picked before it is made, then given to
    // it in that order; its page opens.
    await mounted.click(document.querySelector('[data-action="create-group"]'));
    const page = () => document.querySelector('[data-group-new]');
    const sections = [...(page()?.querySelectorAll('h3') ?? [])].map((h) => h.textContent);
    expect(sections).toEqual(['Policies', 'Members']); // Info has no title: the page's own is above it
    expect(page()?.querySelector('[data-instance-name]')?.textContent).toBe('New group');
    expect(document.querySelector('[data-group]')).toBeNull(); // the list is left
    await mounted.type(document.querySelector('[aria-label="Group name"]'), 'Recruiters');
    await mounted.click(document.querySelector('[data-action="add-members"]'));
    await mounted.click(document.querySelector('[data-attach-option="usr_bob"] button'));
    await mounted.flush();
    expect(document.querySelector('[data-member="usr_bob"]')).not.toBeNull();
    await mounted.click(document.querySelector('[data-action="add-policies"]'));
    await mounted.click(document.querySelector('[data-role-option="pol_1"] input'));
    await mounted.click(document.querySelector('[data-action="add-picked"]'));
    await mounted.flush();
    expect(document.querySelector('[data-policy="pol_1"]')).not.toBeNull();
    expect(api.createGroup).not.toHaveBeenCalled();
    await mounted.click(document.querySelector('[data-action="create"]'));
    await mounted.flush();
    expect(api.createGroup).toHaveBeenCalledWith({ name: 'Recruiters', scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
    expect(api.addMember).toHaveBeenCalledWith('grp_ws', 'usr_bob');
    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'pol_1', principal_id: 'grp_ws', scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
    expect(api.attach.mock.invocationCallOrder[0]).toBeLessThan(api.addMember.mock.invocationCallOrder[0]);
    expect(document.querySelector('[data-group-detail]')?.getAttribute('data-group-detail')).toBe('grp_ws');
    expect([...document.querySelectorAll('[data-group-detail] h3')].map((h) => h.textContent)).toEqual(['Policies', 'Members']);
  });

  it('adds a member of the scope, lists the group’s policies at every level, attaches here, and maps no IdP claim', async () => {
    const api = workspaceApi();
    await show(api, owned.id);
    await mounted!.click(document.querySelector('[data-action="add-members"]'));
    expect([...document.querySelectorAll('[data-attach-option]')].map((o) => o.getAttribute('data-attach-option'))).toEqual(['usr_bob']);
    await mounted!.click(document.querySelector('[data-attach-option="usr_bob"] button'));
    await mounted!.flush();
    expect(api.addMember).toHaveBeenCalledWith('grp_ws', 'usr_bob');

    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: 'grp_ws' });
    expect(document.querySelector('[data-holding]')?.textContent).toContain('Graph reader');
    await mounted!.click(document.querySelector('[data-action="add-policies"]'));
    // Graph reader is held here already: only Writer is offered.
    expect([...document.querySelectorAll('[data-role-option]')].map((o) => o.getAttribute('data-role-option'))).toEqual(['pol_2']);
    await mounted!.click(document.querySelector('[data-role-option="pol_2"] input'));
    await mounted!.click(document.querySelector('[data-action="add-picked"]'));
    await mounted!.flush();
    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'pol_2', principal_id: 'grp_ws', scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });

    expect(document.querySelector('[data-idp-mappings]')).toBeNull();
  });

  it('changes neither the members nor the existence of a group owned above', async () => {
    await show(workspaceApi(), fromOrg.id);
    expect(buttonNamed('Delete Org analysts')).toBeNull();
    expect((document.querySelector('[aria-label="Group name"]') as HTMLInputElement).readOnly).toBe(true);
    expect(document.querySelector('[data-action="add-members"]')).toBeNull();
    expect(document.querySelector('[data-action="add-policies"]')).not.toBeNull();
  });

  it('shows its fields as Settings does: its name and its description', async () => {
    await show(workspaceApi(), owned.id);
    const input = (label: string) => document.querySelector(`[aria-label="${label}"]`) as HTMLInputElement;
    for (const label of ['Group name', 'Group description']) {
      expect(input(label).classList.contains('account-profile-field-input')).toBe(true);
      expect(input(label).disabled).toBe(false);
    }
    expect(input('Group name').readOnly).toBe(false);
    // Its owner, its kind and its id are above, beside and under its name: no field of their own.
    expect(input('Owned by')).toBeNull();
    expect(input('Kind')).toBeNull();
    expect(input('ID')).toBeNull();
    // Above Info: its name, its id, what it is.
    const header = document.querySelector('[data-group-detail] [data-instance-header]');
    expect(header?.querySelector('[data-instance-name]')?.textContent).toBe(owned.name);
    expect(header?.querySelector('[data-instance-ids]')?.textContent).toBe(owned.id);
    expect(header?.querySelector('[data-instance-meta]')?.textContent).toContain('Owned by');
    expect(header?.querySelector('[data-action="save"]')).not.toBeNull();
  });

  it('says when each member joined it', async () => {
    const withDates = {
      ...owned,
      members: [
        { ...principal({ id: 'usr_bob', name: 'Bob' }), joined_at: '2026-11-20T09:30:00+00:00' },
        { ...principal({ id: 'usr_old', name: 'Old' }), joined_at: null },
      ],
    };
    await show(workspaceApi({ getGroup: vi.fn(() => Promise.resolve(withDates)) }), owned.id);
    const headers = [...document.querySelectorAll('[aria-label="Members"] th')].map((th) => th.textContent);
    expect(headers).toContain('Joined at');
    expect(document.querySelector('[data-member="usr_bob"] [data-joined]')?.textContent).toBe('2026-11-20');
    expect(document.querySelector('[data-member="usr_old"] [data-joined]')?.textContent).toBe('—');
  });

  it('renames a group it owns, and shows the new name', async () => {
    const renamed = { ...owned, name: 'Talent' };
    const api = workspaceApi({ updateGroup: vi.fn(() => Promise.resolve(renamed)) });
    await show(api, owned.id);
    const input = document.querySelector('[aria-label="Group name"]') as HTMLInputElement;
    expect(input.value).toBe('Recruiters');
    expect((document.querySelector('[data-action="save"]') as HTMLButtonElement).disabled).toBe(true);
    await mounted!.type(input, '  Talent ');
    await mounted!.click(document.querySelector('[data-action="save"]'));
    await mounted!.flush();
    expect(api.updateGroup).toHaveBeenCalledWith('grp_ws', { name: 'Talent' });
    expect((document.querySelector('[aria-label="Group name"]') as HTMLInputElement).value).toBe('Talent');
  });

  it('says what it is for: its description, saved with its name', async () => {
    const described = { ...owned, description: 'Who hires.' };
    const saved = { ...owned, description: 'Who hires, and onboards.' };
    const api = workspaceApi({
      getGroup: vi.fn(() => Promise.resolve(described)),
      updateGroup: vi.fn(() => Promise.resolve(saved)),
    });
    await show(api, owned.id);
    const field = () => document.querySelector('[aria-label="Group description"]') as HTMLTextAreaElement;
    expect(field().value).toBe('Who hires.');
    expect(field().readOnly).toBe(false);
    await mounted!.type(field(), 'Who hires, and onboards.');
    await mounted!.click(document.querySelector('[data-action="save"]'));
    await mounted!.flush();
    expect(api.updateGroup).toHaveBeenCalledWith('grp_ws', { description: 'Who hires, and onboards.' });
    expect(field().value).toBe('Who hires, and onboards.');
  });

  it('creates a group with what it is for', async () => {
    const api = workspaceApi();
    mounted = await mount(GroupsView, { api, can: admin, scope: wsScope, directory: fakeDirectory([member()]) });
    await mounted.flush();
    await mounted.click(document.querySelector('[data-action="create-group"]'));
    await mounted.type(document.querySelector('[aria-label="Group name"]'), 'Recruiters');
    await mounted.type(document.querySelector('[aria-label="Group description"]'), 'Who hires.');
    await mounted.click(document.querySelector('[data-action="create"]'));
    await mounted.flush();
    expect(api.createGroup).toHaveBeenCalledWith({
      name: 'Recruiters',
      scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1',
      description: 'Who hires.',
    });
  });

  it('offers no rename without iam:UpdateGroup, and keeps the form open when it fails', async () => {
    await show(workspaceApi(), owned.id);
    expect(document.querySelector('[data-action="save"]')).not.toBeNull();
    await mounted!.unmount();
    mounted = null;

    const refused = (action: string) => action !== 'iam:UpdateGroup' && admin(action);
    mounted = await mount(GroupsView, { api: workspaceApi(), can: refused, scope: wsScope, directory: fakeDirectory([member()]) });
    await mounted.flush();
    await mounted.click(document.querySelector(`[data-group="${owned.id}"] button[data-action="open"]`));
    await mounted.flush();
    expect(document.querySelector('[data-action="save"]')).toBeNull();
    expect((document.querySelector('[aria-label="Group name"]') as HTMLInputElement).readOnly).toBe(true);
    await mounted.unmount();
    mounted = null;

    const failing = workspaceApi({ updateGroup: vi.fn(() => Promise.reject(new IamAdminError('Not allowed to rename it', 403))) });
    await show(failing, owned.id);
    await mounted!.type(document.querySelector('[aria-label="Group name"]'), 'Talent');
    await mounted!.click(document.querySelector('[data-action="save"]'));
    await mounted!.flush();
    expect(mounted!.host.querySelector('[role="alert"]')?.textContent).toContain('Not allowed to rename it');
    expect((document.querySelector('[aria-label="Group name"]') as HTMLInputElement).value).toBe('Talent');
  });
});

describe('A group’s page', () => {
  const W = 'abi:nexus:organization/acme/nexus:workspace/ws-1';
  const g = group({ id: 'grp_g', name: 'G', owner_scope: W, members: [principal({ id: 'usr_bob', display_name: 'Bob' })] });
  const analysts = attachment({ id: 'a1', policy_id: 'pol_w', policy_name: 'W analysts', principal_id: 'grp_g', principal: g, scope: W, policy_owner_scope: W });
  const project = attachment({ id: 'a2', policy_id: 'pol_p', policy_name: 'P1 readers', principal_id: 'grp_g', principal: g, scope: `${W}/dev_people:project/p1`, policy_owner_scope: W });

  function groupApi() {
    return fakeApi({
      listGroups: vi.fn(() => Promise.resolve({ items: [g] })),
      getGroup: vi.fn(() => Promise.resolve(g)),
      listAttachments: vi.fn(() => Promise.resolve({ items: [project, analysts] })),
      attachable: vi.fn(() => Promise.resolve({ items: [] })),
      detach: vi.fn(() => Promise.resolve(undefined)),
      resources: vi.fn(() => Promise.resolve({ items: [] })),
      access: vi.fn(() => Promise.resolve({ actions: { 'iam:DetachPolicy': true } })),
    });
  }

  it('lists its members, each opening their page, and its attachments at every level, the page’s own first', async () => {
    const api = groupApi();
    const open = { person: vi.fn(), group: vi.fn() };
    const onFocus = vi.fn();
    mounted = await mount(GroupsView, { api, can: allowAll, scope: PLATFORM_ACCESS_SCOPE, directory: EMPTY_DIRECTORY, open, focus: 'grp_g', onFocus, loadProviders: () => Promise.resolve(providers) });
    await mounted.flush();
    await mounted.flush();

    expect(document.querySelector('[data-group-detail="grp_g"]')).not.toBeNull();
    expect(document.querySelector('[data-group-detail] [data-instance-meta]')?.textContent).toContain('Owned by Workspace ws-1 (acme)');
    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: 'grp_g' });
    const levels = [...document.querySelectorAll('[data-holding]')].map((r) => r.querySelector('td:nth-child(2)')?.textContent);
    expect(levels).toEqual(['Workspace ws-1 (acme)', 'Project p1 (ws-1, acme)']);
    await mounted.click(document.querySelector('[aria-label="Open Bob"]'));
    expect(open.person).toHaveBeenCalledWith('usr_bob', 'Bob');

    // Detached at its own level, where `access` there says the caller may.
    await mounted.click(document.querySelector('[aria-label="Detach P1 readers at Project p1 (ws-1, acme)"]'));
    await mounted.click(buttonNamed('Confirm detach'));
    expect(api.detach).toHaveBeenCalledWith({ policy_id: 'pol_p', principal_id: 'grp_g', scope: `${W}/dev_people:project/p1` });
    expect(api.access).toHaveBeenCalledWith(`${W}/dev_people:project/p1`);

    await mounted.click(buttonNamed('Groups'));
    expect(onFocus).toHaveBeenLastCalledWith(null);
    expect(document.querySelector('[data-group="grp_g"]')).not.toBeNull();
  });

  it('opens from a row of the list', async () => {
    const api = groupApi();
    const onFocus = vi.fn();
    mounted = await mount(GroupsView, { api, can: allowAll, scope: PLATFORM_ACCESS_SCOPE, directory: EMPTY_DIRECTORY, onFocus, loadProviders: () => Promise.resolve(providers) });
    await mounted.flush();
    await mounted.click(document.querySelector('[data-group="grp_g"] button[data-action="open"]'));
    expect(onFocus).toHaveBeenCalledWith('grp_g');
    expect(document.querySelector('[data-group-detail="grp_g"]')).not.toBeNull();
  });

  it('says so when IAM lets the caller list none of its attachments', async () => {
    const api = groupApi();
    // Across levels IAM answers what the caller may list: here, nothing.
    (api as unknown as Record<string, unknown>).listAttachments = vi.fn().mockResolvedValue({ items: [] });
    mounted = await mount(GroupsView, { api, can: allowAll, scope: PLATFORM_ACCESS_SCOPE, directory: EMPTY_DIRECTORY, focus: 'grp_g', loadProviders: () => Promise.resolve(providers) });
    await mounted.flush();
    await mounted.flush();
    expect(mounted.host.textContent).toContain('Nothing you may list is attached to this group.');
    expect(document.querySelector('[role="alert"]')).toBeNull();
  });

  it('opens from a link though the scope’s list of groups cannot be read', async () => {
    const api = groupApi();
    (api as unknown as Record<string, unknown>).listGroups = vi.fn(() => Promise.reject(new IamAdminError('IAM is not available on this server.', 503)));
    mounted = await mount(GroupsView, { api, can: allowAll, scope: PLATFORM_ACCESS_SCOPE, directory: EMPTY_DIRECTORY, focus: 'grp_g', loadProviders: () => Promise.resolve(providers) });
    await mounted.flush();
    await mounted.flush();
    expect(document.querySelector('[data-group-detail="grp_g"]')).not.toBeNull();
    expect(document.querySelector('[data-holding="pol_w"]')).not.toBeNull();
  });
});

