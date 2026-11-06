// @vitest-environment jsdom
/**
 * A person's page, for each viewer: what IAM lets them list is what the API answers them (the
 * API's tests check those answers per viewer, `iam_admin` `..._access_views_test.py`); the page
 * shows those rows at every level, and offers the detach and the role change where `access`
 * at each row's level says the viewer may.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { AttachmentView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { useAuthStore } from '@/stores/auth';
import type { AccessDirectory } from '../access-directory';
import { ORG, WS, attachment, fakeApi, member, wsScope } from '../access-fixtures';
import { PLATFORM_ACCESS_SCOPE, organizationAccessScope, workspaceAccessScope } from '../access-scope';
import { principal } from '../service-fixtures';
import { PersonView } from './person';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  useAuthStore.setState({ user: null });
});

/** Bob among the members of acme and of ws-1, as `userId` there (his IAM id unless linked). */
function bobMember(userId = 'usr_bob'): AccessDirectory & { asked: string[] } {
  const asked: string[] = [];
  return {
    asked,
    members: (scope) => {
      asked.push(scope.workspaceId ?? scope.organizationId ?? 'platform');
      const there = scope.organizationId === 'acme' || scope.workspaceId === 'ws-1';
      return Promise.resolve(there ? [member({ userId, email: 'bob-9a4bcd@example.com' })] : []);
    },
  };
}

const DEMO_ORG = 'abi:nexus:organization/demo-org';
const DEMO = `${DEMO_ORG}/nexus:workspace/demo`;
const NAMES: Record<string, string> = { [ORG]: 'Acme', [WS]: 'W', [DEMO_ORG]: 'Demo org', [DEMO]: 'Ontology demo' };

const bob = principal({ id: 'usr_bob', display_name: 'Bob', email: 'bob-9a4bcd@example.com' });
const g = principal({ id: 'grp_g', kind: 'group', name: 'G', display_name: null, email: null, owner_scope: WS });
const held = (over: Partial<AttachmentView>) =>
  attachment({ principal_id: bob.id, principal: bob, policy_owner_scope: 'abi:', ...over });

const memberAtOrg = held({ id: 'a_org', policy_id: 'builtin.member', policy_name: 'Member', scope: ORG });
const memberAtW = held({ id: 'a_w', policy_id: 'builtin.member', policy_name: 'Member', scope: WS });
const memberAtDemo = held({ id: 'a_demo', policy_id: 'builtin.member', policy_name: 'Member', scope: DEMO });
const bfo = held({ id: 'a_bfo', policy_id: 'pol_bfo', policy_name: 'Bob: BFO only', scope: DEMO, policy_owner_scope: DEMO });
const platformMember = held({ id: 'a_pm', policy_id: 'builtin.platform.member', policy_name: 'Platform member', scope: null });
const analysts = attachment({ id: 'a_g', policy_id: 'pol_w', policy_name: 'W analysts', principal_id: g.id, principal: g, scope: WS, policy_owner_scope: WS });

/** What IAM answers a viewer: the rows they may list, and their rights by level. */
function apiFor(rows: AttachmentView[], groups: (typeof g)[], rights: Record<string, string[]>) {
  return fakeApi({
    listAttachments: vi.fn(({ principal_id }: { principal_id: string }) =>
      principal_id === g.id
        ? Promise.resolve({ items: groups.length ? [analysts] : [] })
        : Promise.resolve({ items: rows }),
    ),
    principalGroups: vi.fn().mockResolvedValue({ items: groups }),
    getPrincipal: vi.fn().mockRejectedValue(new IamAdminError('Not found.', 404)),
    resources: vi.fn(({ scope }: { scope: string }) =>
      Promise.resolve({ items: NAMES[scope] ? [{ name: scope, id: '', label: NAMES[scope], description: '' }] : [] }),
    ),
    access: vi.fn((scope?: string) =>
      Promise.resolve({ actions: Object.fromEntries((rights[scope ?? 'abi:'] ?? []).map((a) => [a, true])) }),
    ),
    detach: vi.fn().mockResolvedValue(undefined),
  });
}

const ADMIN = ['iam:ListAttachments', 'iam:AttachPolicy', 'iam:DetachPolicy', 'iam:ListPolicies'];
const row = (policy: string, level: string | null) =>
  document.querySelector(`[data-holding="${policy}"][data-level="${level ?? ''}"]`);
const field = (label: string) => document.querySelector(`[aria-label="${label}"]`);
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

async function show(api: ReturnType<typeof apiFor>, can: (a: string) => boolean, scope = PLATFORM_ACCESS_SCOPE, more = {}) {
  const open = { person: vi.fn(), group: vi.fn() };
  const changeRole = vi.fn().mockResolvedValue(undefined);
  mounted = await mount(PersonView, {
    api,
    can,
    scope,
    directory: bobMember(),
    open,
    personId: bob.id,
    label: 'bob',
    onClose: vi.fn(),
    changeRole,
    // The workspaces to view them in: none unless a test says (the server's answer, not fetched here).
    viewable: () => Promise.resolve([]),
    ...more,
  });
  await mounted.flush();
  await mounted.flush();
  await mounted.flush();
  return { open, changeRole };
}

describe('A person’s page', () => {
  it('shows the platform admin everything Bob holds, at every level, and through which group', async () => {
    const everywhere = { 'abi:': ADMIN, [ORG]: ADMIN, [WS]: ADMIN, [DEMO]: ADMIN };
    const api = apiFor([memberAtOrg, memberAtW, memberAtDemo, bfo, platformMember], [g], everywhere);
    const { open, changeRole } = await show(api, () => true);

    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: 'usr_bob' });
    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: 'grp_g' });
    expect(document.querySelector('.access-person-name')?.textContent).toBe('Bob');
    // Its level, named as the Owner column names containers.
    expect(row('builtin.member', ORG)?.textContent).toContain('Organization Acme');
    expect(row('builtin.member', WS)?.textContent).toContain('Workspace W (Acme)');
    expect(row('builtin.member', DEMO)?.textContent).toContain('Workspace Ontology demo (Demo org)');
    // What comes with a role says which: Member at each workspace brings Platform member.
    expect(row('builtin.platform.member', null)?.textContent).toContain(
      'Comes with Member at Workspace W (Acme), Member at Workspace Ontology demo (Demo org)',
    );
    // A policy links to itself at its owner.
    const link = row('pol_bfo', DEMO)?.querySelector('a');
    expect(link?.getAttribute('href')).toBe('/workspace/demo/settings/permissions?section=policies&policy=pol_bfo');
    // Through a group: which, opening its page.
    const through = row('pol_w', WS);
    expect(through?.getAttribute('data-via')).toBe('grp_g');
    await mounted!.click(through!.querySelector('button'));
    expect(open.group).toHaveBeenCalledWith('grp_g', 'G');
    expect(document.querySelector('[data-group-of="grp_g"]')?.textContent).toContain('Workspace W (Acme)');

    // Detach where IAM says the viewer may; a role is a membership, changed as on Members.
    await mounted!.click(field('Detach Bob: BFO only at Workspace Ontology demo (Demo org)'));
    await mounted!.click(button('Confirm detach') ?? null);
    expect(api.detach).toHaveBeenCalledWith({ policy_id: 'pol_bfo', principal_id: 'usr_bob', scope: DEMO });
    expect(field('Detach W analysts at Workspace W (Acme)')).toBeNull();
    expect(field('Detach Platform member at Everywhere')).toBeNull();
    await mounted!.select(field('Role at Organization Acme'), 'admin');
    expect(changeRole).toHaveBeenCalledWith({ level: 'organization', organizationId: 'acme' }, 'usr_bob', 'admin');
  });

  it('attaches a policy to them at the page’s level, or at another level they belong to', async () => {
    const api = apiFor([memberAtOrg, memberAtW, bfo, platformMember], [], { 'abi:': ADMIN, [ORG]: ADMIN, [WS]: ADMIN });
    const offered = [
      { id: 'pol_x', name: 'Readers', description: '', managed: false },
      { id: 'builtin.viewer', name: 'Viewer', description: '', managed: true },
      { id: 'builtin.api', name: 'Nexus API', description: '', managed: true },
    ];
    const extra = api as unknown as Record<string, unknown>;
    extra.attachable = vi.fn().mockResolvedValue({ items: offered });
    extra.attach = vi.fn().mockResolvedValue(undefined);
    await show(api, () => true);
    // This page's level first, then the platform's and each where they hold a role, where the
    // viewer may attach (not Ontology demo: no right there).
    const levels = [...(field('Attach at') as HTMLSelectElement).options].map((o) => o.value);
    expect(levels).toEqual(['abi:', ORG, WS]);
    expect(extra.attachable).toHaveBeenLastCalledWith('');
    // The person is fixed, as a user: no built-in role (a membership), no service account's policy.
    expect(field('Principal to attach to')).toBeNull();
    const policies = () =>
      [...(field('Policy to attach') as HTMLSelectElement).options].map((o) => o.value).filter(Boolean);
    expect(policies()).toEqual(['pol_x']);
    await mounted!.select(field('Attach at'), WS);
    await mounted!.flush();
    expect(extra.attachable).toHaveBeenLastCalledWith(WS);
    await mounted!.select(field('Policy to attach'), 'pol_x');
    const before = (api.listAttachments as ReturnType<typeof vi.fn>).mock.calls.length;
    await mounted!.click(button('Attach policy') ?? null);
    await mounted!.flush();
    expect(extra.attach).toHaveBeenCalledWith({ policy_id: 'pol_x', principal_id: bob.id, scope: WS });
    // The page reads what they hold again: the new row shows at once.
    expect((api.listAttachments as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(before);
  });

  it('offers no attach where the viewer may attach nowhere they belong', async () => {
    const api = apiFor([memberAtW], [], { [WS]: ['iam:ListAttachments'] });
    await show(api, () => false, wsScope);
    expect(document.querySelector('[aria-label="Attach a policy to them"]')).toBeNull();
  });

  it('shows an organization’s admin what is inside it, from the workspace’s page too', async () => {
    const inside = { [ORG]: ADMIN, [WS]: ADMIN };
    const api = apiFor([memberAtOrg, memberAtW], [g], inside);
    await show(api, (a) => ADMIN.includes(a), workspaceAccessScope('acme', 'ws-1'));

    expect(row('builtin.member', ORG)).not.toBeNull();
    expect(row('builtin.member', WS)).not.toBeNull();
    expect(row('pol_bfo', DEMO)).toBeNull();
    expect(row('pol_w', WS)).not.toBeNull();
    expect(field('Role at Workspace W (Acme)')).not.toBeNull();
    expect(api.access).not.toHaveBeenCalledWith(DEMO);
  });

  it('shows a workspace’s admin what IAM lets them list, changing nothing above their workspace', async () => {
    const api = apiFor([memberAtW], [g], { [WS]: ADMIN });
    await show(api, (a) => ADMIN.includes(a), workspaceAccessScope('acme', 'ws-1'));

    expect(row('builtin.member', WS)).not.toBeNull();
    expect(row('builtin.member', ORG)).toBeNull();
    expect(field('Role at Workspace W (Acme)')).not.toBeNull();
    // A policy of their workspace links to it there.
    expect(row('pol_w', WS)?.querySelector('a')?.getAttribute('href')).toBe(
      '/workspace/ws-1/settings/permissions?section=policies&policy=pol_w',
    );
  });

  it('shows a member nothing', async () => {
    const api = apiFor([], [], {});
    await show(api, () => false, organizationAccessScope('acme'));
    expect(mounted!.host.textContent).toContain('They hold nothing you may list.');
    expect(mounted!.host.textContent).toContain('In no group you may see.');
    expect(document.querySelector('[data-holding]')).toBeNull();
    expect(document.querySelectorAll('select, [aria-label^="Detach"]')).toHaveLength(0);
    // Named as the page that opened it named them.
    expect(document.querySelector('.access-person-name')?.textContent).toBe('bob');
  });

  it('changes the role of an account linked from the old login as its members name it, whatever opened the page', async () => {
    const api = apiFor([memberAtW], [], { [WS]: ADMIN });
    const directory = bobMember('user-7');
    const { changeRole } = await show(api, (a) => ADMIN.includes(a), workspaceAccessScope('acme', 'ws-1'), { directory });
    // Found among ws-1's members by his email: the membership route takes that account.
    expect(directory.asked).toEqual(['ws-1']);
    await mounted!.select(field('Role at Workspace W (Acme)'), 'viewer');
    expect(changeRole).toHaveBeenCalledWith({ level: 'workspace', workspaceId: 'ws-1' }, 'user-7', 'viewer');
  });

  it('offers no change of one’s own role, linked account included', async () => {
    useAuthStore.setState({ user: { id: 'user-7' } as never });
    const api = apiFor([memberAtW], [], { [WS]: ADMIN });
    await show(api, (a) => ADMIN.includes(a), workspaceAccessScope('acme', 'ws-1'), { directory: bobMember('user-7') });
    expect(row('builtin.member', WS)).not.toBeNull();
    expect(field('Role at Workspace W (Acme)')).toBeNull();
  });

  it('changes no role where the person is not found among the members', async () => {
    const api = apiFor([memberAtW], [], { [WS]: ADMIN });
    const nobody: AccessDirectory = { members: () => Promise.resolve([]) };
    await show(api, (a) => ADMIN.includes(a), workspaceAccessScope('acme', 'ws-1'), { directory: nobody });
    expect(row('builtin.member', WS)).not.toBeNull();
    expect(field('Role at Workspace W (Acme)')).toBeNull();
  });
});

describe('View as, on a person’s page', () => {
  const ALPHA = { id: 'ws-1', name: 'Alpha', organization: { id: 'acme', name: 'Acme' } };
  const BRAVO = { id: 'ws-2', name: 'Bravo', organization: { id: 'acme', name: 'Acme' } };
  const rights = { 'abi:': ADMIN, [WS]: ADMIN };

  it('offers no button when the server lists no workspace to view them in', async () => {
    await show(apiFor([memberAtW], [], rights), () => true, wsScope);
    expect(button('View as Bob')).toBeUndefined();
  });

  it('offers the button, then the workspaces with the page’s workspace preselected', async () => {
    await show(apiFor([memberAtW], [], rights), () => true, wsScope, { viewable: () => Promise.resolve([BRAVO, ALPHA]) });
    expect(button('View as Bob')).toBeDefined();
    expect(document.querySelector('[aria-label="Workspace to view"]')).toBeNull();
    await mounted!.click(button('View as Bob')!);
    const picker = field('Workspace to view') as HTMLSelectElement;
    expect([...picker.options].map((o) => o.value)).toEqual(['ws-2', 'ws-1']);
    expect(picker.value).toBe('ws-1');
  });

  it('asks about the person by their IAM id', async () => {
    const viewable = vi.fn().mockResolvedValue([ALPHA]);
    await show(apiFor([memberAtW], [], rights), () => true, PLATFORM_ACCESS_SCOPE, { viewable });
    expect(viewable).toHaveBeenCalledWith('usr_bob');
  });
});
