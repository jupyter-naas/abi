// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { attachment, fakeApi, fakeDirectory, member, orgScope, wsScope } from '../access-fixtures';
import { PLATFORM_ACCESS_SCOPE } from '../access-scope';
import { group, principal } from '../service-fixtures';
import { peopleAt } from './people-model';
import { PeopleView } from './people';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const field = (label: string) => document.querySelector(`[aria-label="${label}"]`);
const row = (id: string) => document.querySelector(`[data-person="${id}"]`);

const bob = member();
const ann = member({ userId: 'usr_ann', name: 'Ann', email: 'ann@example.com', role: 'admin', inherited: true });
const analysts = principal({ id: 'grp_1', kind: 'group', name: 'Analysts', display_name: null, email: null });
const recruiters = attachment({ id: 'att_r', policy_id: 'pol_r', policy_name: 'Recruiters', principal_id: 'usr_bob', principal: principal({ id: 'usr_bob', display_name: 'Bob' }), scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
const roleRow = attachment({ id: 'att_m', policy_id: 'builtin.member', policy_name: 'Member', principal_id: 'usr_bob', scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
const groupHolds = attachment({ id: 'att_g', policy_id: 'pol_a', policy_name: 'Analysis', principal_id: 'grp_1', principal: analysts, scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
const elsewhere = attachment({ id: 'att_x', scope: 'abi:nexus:organization/acme/nexus:workspace/ws-2' });

describe('peopleAt', () => {
  it('shows each person once: their role, their policies here and what their groups give them', () => {
    const rows = peopleAt(
      [recruiters, roleRow, groupHolds],
      [bob, ann],
      [group({ id: 'grp_1', name: 'Analysts', members: [principal({ id: 'usr_bob', display_name: 'Bob' })] })],
    );
    expect(rows.map((r) => r.id)).toEqual(['usr_ann', 'usr_bob', 'grp_1']);
    const [annRow, bobRow, groupRow] = rows;
    expect(annRow).toMatchObject({ role: 'admin', inherited: true, direct: [] });
    expect(bobRow.role).toBe('member');
    expect(bobRow.direct.map((a) => a.policy_id)).toEqual(['pol_r']);
    expect(bobRow.viaGroups).toEqual([{ groupId: 'grp_1', groupLabel: 'Analysts', policies: [{ id: 'pol_a', name: 'Analysis' }] }]);
    expect(groupRow.direct.map((a) => a.policy_id)).toEqual(['pol_a']);
  });

  it('joins a member whose account id is not their IAM id (a linked account) by email', () => {
    const owner = member({ userId: 'user-1', name: 'Dev Admin', email: 'admin@example.com', role: 'owner' });
    const held = attachment({ policy_id: 'pol_r', policy_name: 'Recruiters', principal_id: 'usr_1', principal: principal({ id: 'usr_1', email: 'admin@example.com', display_name: 'Dev Admin' }) });
    const role = attachment({ id: 'att_o', policy_id: 'builtin.owner', principal_id: 'usr_1', principal: principal({ id: 'usr_1', email: 'admin@example.com' }) });
    const rows = peopleAt([held, role], [owner], []);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ id: 'user-1', role: 'owner', member: true });
    expect(rows[0].direct.map((a) => a.policy_id)).toEqual(['pol_r']);
  });

  it('reads a role from its attachment where there is no member list (the platform)', () => {
    const admin = attachment({ policy_id: 'builtin.admin', principal_id: 'usr_root', principal: principal({ id: 'usr_root', display_name: 'Root' }), scope: null });
    expect(peopleAt([admin], [], [])[0]).toMatchObject({ id: 'usr_root', role: 'admin', member: false, direct: [] });
  });
});

function peopleApi(over: Record<string, unknown> = {}) {
  return fakeApi({
    listAttachments: vi.fn().mockResolvedValue({ items: [recruiters, roleRow, groupHolds, elsewhere] }),
    getGroup: vi.fn().mockResolvedValue(group({ id: 'grp_1', name: 'Analysts', members: [principal({ id: 'usr_bob' })] })),
    attachable: vi.fn().mockResolvedValue({ items: [{ id: 'pol_r', name: 'Recruiters', description: '', managed: false }] }),
    attach: vi.fn().mockResolvedValue(recruiters),
    detach: vi.fn().mockResolvedValue(undefined),
    ...over,
  });
}

describe('PeopleView', () => {
  it('lists who holds what in the workspace, the organization’s roles read-only', async () => {
    const api = peopleApi();
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory: fakeDirectory([bob, ann]), changeRole: vi.fn() });
    await mounted.flush();

    expect(api.listAttachments).toHaveBeenCalledWith({ scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
    expect(row('usr_bob')?.textContent).toContain('Recruiters');
    expect(row('usr_bob')?.textContent).toContain('Analysts: Analysis');
    expect(row('usr_ann')?.textContent).toContain('from organization');
    expect(field('Role of Ann')).toBeNull();
    // Another workspace's attachment is not this one's.
    expect(document.querySelector('[data-held="pol_1"]')).toBeNull();
  });

  it('changes a role through the membership code, and detaches a policy', async () => {
    const api = peopleApi();
    const changeRole = vi.fn().mockResolvedValue(undefined);
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory: fakeDirectory([bob]), changeRole });
    await mounted.flush();

    const select = field('Role of Bob') as HTMLSelectElement;
    expect([...select.options].map((o) => o.value)).toEqual(['member', 'viewer', 'admin']);
    select.value = 'admin';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted.flush();
    expect(changeRole).toHaveBeenCalledWith({ level: 'workspace', workspaceId: 'ws-1' }, 'usr_bob', 'admin');

    await mounted.click(field('Detach Recruiters from Bob'));
    await mounted.click(button('Confirm detach') ?? null);
    expect(api.detach).toHaveBeenCalledWith({ policy_id: 'pol_r', principal_id: 'usr_bob', scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
  });

  it('attaches a policy to a person of the scope', async () => {
    const api = peopleApi();
    mounted = await mount(PeopleView, { api, can: () => true, scope: orgScope, directory: fakeDirectory([bob]), changeRole: vi.fn() });
    await mounted.flush();
    expect([...(field('Role of Bob') as HTMLSelectElement).options].map((o) => o.value)).toEqual(['member', 'admin']);
    await mounted.type(field('Principal to attach to'), 'usr_bob');
    await mounted.select(field('Policy to attach'), 'pol_r');
    await mounted.click(button('Attach policy') ?? null);
    expect(api.attach).toHaveBeenCalledWith({ policy_id: 'pol_r', principal_id: 'usr_bob', scope: 'abi:nexus:organization/acme' });
  });

  it('shows the platform’s holders, everywhere attached, with no role to change', async () => {
    const root = attachment({ id: 'att_root', policy_id: 'builtin.platform_admin', policy_name: 'Platform admin', principal_id: 'usr_root', principal: principal({ id: 'usr_root', display_name: 'Root' }), scope: null });
    const api = peopleApi({ listAttachments: vi.fn().mockResolvedValue({ items: [root, elsewhere] }) });
    mounted = await mount(PeopleView, { api, can: () => true, scope: PLATFORM_ACCESS_SCOPE, directory: fakeDirectory([]) });
    await mounted.flush();
    expect(api.listAttachments).toHaveBeenCalledWith({});
    expect(row('usr_root')?.textContent).toContain('Platform admin');
    expect(row(elsewhere.principal_id)).toBeNull();
    expect(document.querySelector('select[aria-label^="Role of"]')).toBeNull();
  });

  it('shows what comes with a role as part of it, with no detach', async () => {
    const companion = attachment({ id: 'att_p', policy_id: 'builtin.platform.member', policy_name: 'Platform member', principal_id: 'usr_bob', principal: principal({ id: 'usr_bob' }), scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' });
    const api = peopleApi({ listAttachments: vi.fn().mockResolvedValue({ items: [recruiters, roleRow, companion] }) });
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory: fakeDirectory([bob]), changeRole: vi.fn() });
    await mounted.flush();
    expect(row('usr_bob')?.querySelector('[data-with-role]')?.textContent).toContain('Platform member');
    expect(document.querySelector('[data-held="builtin.platform.member"]')).toBeNull();
    expect(field('Detach Platform member from Bob')).toBeNull();
    expect(field('Detach Recruiters from Bob')).not.toBeNull();
  });

  it('says what it could not read, and shows the rest', async () => {
    const api = peopleApi({ getGroup: vi.fn().mockRejectedValue(new Error('HTTP 500')) });
    const directory = { members: () => Promise.reject(new Error('You do not have permission to do this.')) };
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory, changeRole: vi.fn() });
    await mounted.flush();
    const notices = [...document.querySelectorAll('[data-people-notice]')].map((n) => n.textContent);
    expect(notices).toEqual([
      'The members could not be read (You do not have permission to do this.): roles are shown from what is attached here, and cannot be changed.',
      'The members of Analysts could not be read (HTTP 500): what the group gives them is not shown.',
    ]);
    expect(row('usr_bob')?.textContent).toContain('Recruiters');
    expect(row('usr_bob')?.querySelector('[data-role]')?.textContent).toBe('Member');
  });

  it('shows no change to a caller who may only list', async () => {
    const api = peopleApi();
    mounted = await mount(PeopleView, { api, can: (a) => a === 'iam:ListAttachments', scope: wsScope, directory: fakeDirectory([bob]) });
    await mounted.flush();
    expect(field('Role of Bob')).toBeNull();
    expect(field('Detach Recruiters from Bob')).toBeNull();
    expect(button('Attach policy')).toBeUndefined();
    expect(api.attachable).not.toHaveBeenCalled();
  });

  it('opens a person’s page from their row, by their IAM id', async () => {
    const linked = member({ userId: 'user-1', name: 'Dev Admin', email: 'admin@example.com', role: 'admin' });
    const held = attachment({ id: 'att_l', policy_id: 'pol_r', policy_name: 'Recruiters', principal_id: 'usr_1', principal: principal({ id: 'usr_1', email: 'admin@example.com' }), scope: wsScope.value });
    const api = peopleApi({ listAttachments: vi.fn().mockResolvedValue({ items: [held, recruiters, groupHolds] }) });
    const open = { person: vi.fn(), group: vi.fn() };
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory: fakeDirectory([bob, linked]), open, changeRole: vi.fn() });
    await mounted.flush();

    await mounted.click(field('Open Dev Admin'));
    expect(open.person).toHaveBeenLastCalledWith('usr_1', 'Dev Admin');
    await mounted.click(field('Open Bob'));
    expect(open.person).toHaveBeenLastCalledWith('usr_bob', 'Bob');
    await mounted.click(field('Open Analysts'));
    expect(open.group).toHaveBeenLastCalledWith('grp_1', 'Analysts');
  });

  it('opens an upgraded account’s page by its IAM id, with only an inherited role here', async () => {
    // An account linked from the old login: Nexus names it user-olivia, IAM usr_olivia. On a
    // workspace page she holds nothing attached here (her role is the organization's).
    const olivia = member({ userId: 'user-olivia', principalId: 'usr_olivia', name: 'Olivia', email: 'olivia@example.com', role: 'admin', inherited: true });
    const api = peopleApi({ listAttachments: vi.fn().mockResolvedValue({ items: [] }) });
    const open = { person: vi.fn(), group: vi.fn() };
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory: fakeDirectory([olivia]), open, changeRole: vi.fn() });
    await mounted.flush();
    await mounted.click(field('Open Olivia'));
    expect(open.person).toHaveBeenLastCalledWith('usr_olivia', 'Olivia');
    // A member whose IAM id nothing says is named, never linked by their Nexus id.
    await mounted.unmount();
    mounted = await mount(PeopleView, {
      api,
      can: () => true,
      scope: wsScope,
      directory: fakeDirectory([member({ userId: 'user-x', name: 'Xavier', email: 'x@example.com' })]),
      open,
      changeRole: vi.fn(),
    });
    await mounted.flush();
    expect(field('Open Xavier')).toBeNull();
  });

  it('shows the person’s page in place of the table', async () => {
    const api = peopleApi({
      principalGroups: vi.fn().mockResolvedValue({ items: [] }),
      listAttachments: vi.fn().mockResolvedValue({ items: [recruiters] }),
      resources: vi.fn().mockResolvedValue({ items: [] }),
      access: vi.fn().mockResolvedValue({ actions: {} }),
    });
    const onClosePerson = vi.fn();
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory: fakeDirectory([bob]), person: { id: 'usr_bob', label: 'Bob' }, onClosePerson });
    await mounted.flush();
    await mounted.flush();
    expect(document.querySelector('[data-person-page="usr_bob"]')).not.toBeNull();
    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: 'usr_bob' });
    await mounted.click(button('People & roles') ?? null);
    expect(onClosePerson).toHaveBeenCalled();
  });

  it('finds anyone at the platform, by a search IAM answers, not only those holding something there', async () => {
    const root = attachment({ id: 'att_root', policy_id: 'builtin.platform_admin', principal_id: 'usr_root', principal: principal({ id: 'usr_root', display_name: 'Root' }), scope: null });
    const carol = principal({ id: 'usr_carol', display_name: 'Carol', email: 'carol@example.com' });
    const api = peopleApi({
      listAttachments: vi.fn().mockResolvedValue({ items: [root] }),
      listPrincipals: vi.fn().mockResolvedValue({ items: [carol], next_after: null }),
    });
    const open = { person: vi.fn(), group: vi.fn() };
    mounted = await mount(PeopleView, { api, can: () => true, scope: PLATFORM_ACCESS_SCOPE, directory: fakeDirectory([]), open, searchDelayMs: 0 });
    await mounted.flush();
    await mounted.type(field('Filter people'), 'car');
    await mounted.flush();
    await mounted.flush();
    expect(api.listPrincipals).toHaveBeenCalledWith('user', undefined, 'car');
    expect(document.querySelector('[data-found="usr_carol"]')?.textContent).toContain('carol@example.com');
    await mounted.click(field('Open Carol'));
    expect(open.person).toHaveBeenCalledWith('usr_carol', 'Carol');
  });

  it('searches nothing for whoever may not list principals, nor below the platform', async () => {
    const api = peopleApi({ listPrincipals: vi.fn() });
    mounted = await mount(PeopleView, { api, can: (a) => a !== 'iam:ListPrincipals', scope: PLATFORM_ACCESS_SCOPE, directory: fakeDirectory([]), searchDelayMs: 0 });
    await mounted.flush();
    await mounted.type(field('Filter people'), 'carol');
    await mounted.flush();
    await mounted.unmount();
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory: fakeDirectory([bob]), searchDelayMs: 0, changeRole: vi.fn() });
    await mounted.flush();
    await mounted.type(field('Filter people'), 'carol');
    await mounted.flush();
    expect(api.listPrincipals).not.toHaveBeenCalled();
  });

  it('names no link where the section it opens is not shown to the caller', async () => {
    const api = peopleApi();
    mounted = await mount(PeopleView, { api, can: () => true, scope: wsScope, directory: fakeDirectory([bob]), open: { person: vi.fn() }, changeRole: vi.fn() });
    await mounted.flush();
    expect(field('Open Bob')).not.toBeNull();
    // No Groups section here: the group is named, not linked.
    expect(field('Open Analysts')).toBeNull();
    expect(row('grp_1')?.textContent).toContain('Analysts');
    expect(row('usr_bob')?.querySelector('[data-via] button')).toBeNull();
  });
});
