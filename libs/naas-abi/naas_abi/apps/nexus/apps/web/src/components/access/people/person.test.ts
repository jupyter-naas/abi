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
import { ORG, WS, attachment, fakeApi, fakeDirectory } from '../access-fixtures';
import { PLATFORM_ACCESS_SCOPE, organizationAccessScope, workspaceAccessScope } from '../access-scope';
import { principal } from '../service-fixtures';
import { PersonView } from './person';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

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
        : rows.length
          ? Promise.resolve({ items: rows })
          : Promise.reject(new IamAdminError('You do not have permission to do this.', 403)),
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
    directory: fakeDirectory([]),
    open,
    personId: bob.id,
    label: 'bob',
    onClose: vi.fn(),
    changeRole,
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
    expect(row('builtin.platform.member', null)?.textContent).toContain('With the role');
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
    expect(mounted!.host.textContent).toContain('You may not list what this person holds.');
    expect(mounted!.host.textContent).toContain('In no group you may see.');
    expect(document.querySelector('[data-holding]')).toBeNull();
    expect(document.querySelectorAll('select, [aria-label^="Detach"]')).toHaveLength(0);
    // Named as the page that opened it named them.
    expect(document.querySelector('.access-person-name')?.textContent).toBe('bob');
  });

  it('changes a role through the account the members name, when it is not the IAM id', async () => {
    const api = apiFor([memberAtW], [], { [WS]: ADMIN });
    const { changeRole } = await show(api, (a) => ADMIN.includes(a), workspaceAccessScope('acme', 'ws-1'), { memberId: 'user-7' });
    await mounted!.select(field('Role at Workspace W (Acme)'), 'viewer');
    expect(changeRole).toHaveBeenCalledWith({ level: 'workspace', workspaceId: 'ws-1' }, 'user-7', 'viewer');
  });
});
