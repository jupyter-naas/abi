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
    listGroups: vi.fn(() => Promise.resolve({ items: [detail] })),
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
  await mounted.click(document.querySelector('[data-group] button.access-row-toggle'));
  await mounted.flush();
}

describe('GroupsView', () => {
  it('lists groups with their member count', async () => {
    mounted = await mount(GroupsView, { api: setup(), can: allowAll, ...platform, loadProviders: () => Promise.resolve(providers) });
    await mounted.flush();
    const row = document.querySelector('[data-group="grp_1"]');
    expect(row?.textContent).toContain('Analysts');
    expect(row?.textContent).toContain('Platform');
    expect(row?.querySelector('.access-num')?.textContent).toBe('1');
  });

  it('adds a member by id', async () => {
    const api = setup();
    await open(api);
    await mounted!.type(document.querySelector('[aria-label="Member id"]'), 'usr_1');
    await mounted!.click(buttonNamed('Add member'));
    expect(api.addMember).toHaveBeenCalledWith('grp_1', 'usr_1');
  });

  it('removes a member', async () => {
    const api = setup();
    await open(api);
    await mounted!.click(buttonNamed('Remove Bob'));
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
    expect(buttonNamed('Add member')).toBeNull();
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
      attachable: vi.fn(() => Promise.resolve({ items: [{ id: 'pol_1', name: 'Graph reader', description: '', managed: false }] })),
      attach: vi.fn(() => Promise.resolve(attachment())),
      ...over,
    });
  }
  // A workspace admin: the IdP mapping actions are the platform's, so `access` says no.
  const admin = (action: string) => !['iam:MapIdpGroup', 'iam:UnmapIdpGroup', 'iam:ListPrincipals'].includes(action);

  async function show(api: ReturnType<typeof workspaceApi>, groupId: string) {
    mounted = await mount(GroupsView, { api, can: admin, scope: wsScope, directory: fakeDirectory([member()]) });
    await mounted.flush();
    await mounted.click(document.querySelector(`[data-group="${groupId}"] button.access-row-toggle`));
    await mounted.flush();
  }

  it('creates a group owned by the workspace', async () => {
    const api = workspaceApi();
    mounted = await mount(GroupsView, { api, can: admin, scope: wsScope, directory: EMPTY_DIRECTORY });
    await mounted.flush();
    expect(api.listGroups).toHaveBeenCalledWith('abi:nexus:organization/acme/nexus:workspace/ws-1');
    await mounted.type(document.querySelector('[aria-label="Group name"]'), 'Recruiters');
    await mounted.click(buttonNamed('Create group'));
    expect(api.createGroup).toHaveBeenCalledWith({ name: 'Recruiters', scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
  });

  it('adds a member of the scope, lists the group’s policies at every level, attaches here, and maps no IdP claim', async () => {
    const api = workspaceApi();
    await show(api, owned.id);
    expect([...document.querySelectorAll(`#${CSS.escape('members-grp_ws')} option`)].map((o) => (o as HTMLOptionElement).value)).toEqual(['usr_bob']);
    await mounted!.type(document.querySelector('[aria-label="Member id"]'), 'usr_bob');
    await mounted!.click(buttonNamed('Add member'));
    expect(api.addMember).toHaveBeenCalledWith('grp_ws', 'usr_bob');

    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: 'grp_ws' });
    expect(document.querySelector('[aria-label="Policies of the group"]')?.textContent).toContain('Graph reader');
    await mounted!.select(document.querySelector('[aria-label="Policy to attach"]'), 'pol_1');
    await mounted!.click(buttonNamed('Attach policy'));
    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'pol_1', principal_id: 'grp_ws', scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });

    expect(mounted!.host.textContent).not.toContain('IdP group claims');
  });

  it('changes neither the members nor the existence of a group owned above', async () => {
    await show(workspaceApi(), fromOrg.id);
    expect(buttonNamed('Delete Org analysts')).toBeNull();
    expect(buttonNamed('Add member')).toBeNull();
    expect(buttonNamed('Attach policy')).not.toBeNull();
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
    expect(document.querySelector('[data-group-owner]')?.textContent).toBe('Owned by Workspace ws-1 (acme)');
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
    await mounted.click(document.querySelector('[data-group="grp_g"] button.access-row-toggle'));
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

