// @vitest-environment jsdom
/**
 * Access, one page per section at every level (`AccessPage`), and a person's page
 * (`PersonPage`): what IAM answers at the scope alone decides what shows. The settings menus
 * list a page exactly when it would show (`visibleSections`, `opensAccess`).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AccessView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { fakeApi, fakeDirectory, orgScope, readerPolicy, wsScope } from './access-fixtures';
import { AccessPage, type AccessHrefs } from './access-page';
import { PLATFORM_ACCESS_SCOPE, type AccessLevel, type AccessScope } from './access-scope';
import { LEVEL_SECTIONS, opensAccess, visibleSections, type AccessSection } from './access-sections';
import { PersonPage } from './people/person-page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

/** The actions of a level's own administration: who holds what, groups, policies. */
const LEVEL = [
  'iam:ListPolicies',
  'iam:CreatePolicy',
  'iam:UpdatePolicy',
  'iam:DeletePolicy',
  'iam:ListAttachments',
  'iam:AttachPolicy',
  'iam:DetachPolicy',
  'iam:ListGroups',
  'iam:CreateGroup',
  'iam:DeleteGroup',
  'iam:AddGroupMember',
  'iam:RemoveGroupMember',
];
/** What only the platform administers: `access` answers it false at any scope. */
const PLATFORM_ONLY = [
  'iam:ListPrincipals',
  'iam:CreateServiceAccount',
  'iam:ListManifests',
  'iam:ApproveManifest',
  'iam:Explain',
  'iam:MapIdpGroup',
  'iam:ListKeys',
  'nexus:ReadSystem',
];

const levelOf = (scope?: string): AccessLevel =>
  scope === undefined ? 'platform' : scope.includes('/nexus:workspace/') ? 'workspace' : 'organization';

/** What each caller holds, by level, as the API answers `access`. */
const CALLERS: Record<string, (level: AccessLevel) => string[]> = {
  'platform admin': (level) => (level === 'platform' ? [...LEVEL, ...PLATFORM_ONLY] : LEVEL),
  'organization admin': (level) => (level === 'platform' ? [] : LEVEL),
  'workspace admin': (level) => (level === 'workspace' ? LEVEL : []),
  'delegated lister': () => ['iam:ListPolicies'],
  // May create policies, not list them: builds one from what it holds.
  'policy builder': () => ['iam:CreatePolicy'],
  // May list who holds what (People & roles before): the policies held here.
  'holdings lister': () => ['iam:ListAttachments'],
  viewer: () => [],
  stranger: () => [],
};

function answer(holds: string[]): AccessView {
  const all = [...LEVEL, ...PLATFORM_ONLY];
  return { actions: Object.fromEntries(all.map((a) => [a, holds.includes(a)])) };
}

function apiFor(caller: string) {
  return fakeApi({
    access: vi.fn((scope?: string) => Promise.resolve(answer(CALLERS[caller](levelOf(scope))))),
    listAttachments: vi.fn().mockResolvedValue({ items: [] }),
    attachable: vi.fn().mockResolvedValue({ items: [] }),
    listGroups: vi.fn().mockResolvedValue({ items: [] }),
    listPolicies: vi.fn().mockResolvedValue({ items: [], next_after: null }),
    listPrincipals: vi.fn().mockResolvedValue({ items: [] }),
    publishers: vi.fn().mockResolvedValue({ scope: '', publishers: [] }),
  });
}

const hrefs: AccessHrefs = {
  page: (section, id) => `/access/${section}${id ? `/${id}` : ''}`,
  person: (id) => `/people/${id}`,
};

async function render(caller: string, scope: AccessScope, section: AccessSection, over: Record<string, unknown> = {}) {
  const api = apiFor(caller);
  const navigate = vi.fn();
  mounted = await mount(AccessPage, { section, scopes: [scope], api, directory: fakeDirectory([]), hrefs, navigate, ...over });
  await mounted.flush();
  await mounted.flush();
  return { api, navigate };
}

const refused = () => document.querySelector('[data-access-refused]');
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

const SCOPES: [AccessLevel, AccessScope, string | undefined][] = [
  ['platform', PLATFORM_ACCESS_SCOPE, undefined],
  ['organization', orgScope, 'abi:nexus:organization/acme'],
  ['workspace', wsScope, 'abi:nexus:organization/acme/nexus:workspace/ws-1'],
];

const ALL_PLATFORM: AccessSection[] = ['policies', 'groups', 'service-accounts', 'approvals', 'simulator', 'audit'];
const CONTAINER: AccessSection[] = ['policies', 'groups'];
const EXPECTED: Record<string, Record<AccessLevel, AccessSection[]>> = {
  'platform admin': { platform: ALL_PLATFORM, organization: CONTAINER, workspace: CONTAINER },
  'organization admin': { platform: [], organization: CONTAINER, workspace: CONTAINER },
  'workspace admin': { platform: [], organization: [], workspace: CONTAINER },
  'delegated lister': { platform: ['policies'], organization: ['policies'], workspace: ['policies'] },
  'policy builder': { platform: ['policies'], organization: ['policies'], workspace: ['policies'] },
  'holdings lister': { platform: ['policies'], organization: ['policies'], workspace: ['policies'] },
  viewer: { platform: [], organization: [], workspace: [] },
  stranger: { platform: [], organization: [], workspace: [] },
};

describe('Access, one page per section at every level', () => {
  for (const caller of Object.keys(CALLERS)) {
    for (const [level, scope, asked] of SCOPES) {
      const expected = EXPECTED[caller][level];
      it(`opens to ${caller} at the ${level} ${expected.length ? expected.join(', ') : 'nothing'}`, async () => {
        for (const section of LEVEL_SECTIONS[level]) {
          const { api } = await render(caller, scope, section);
          expect(api.access).toHaveBeenCalledWith(asked);
          expect(document.querySelector(`[data-section="${section}"]`), section).not.toBeNull();
          expect(!refused(), `${caller} › ${section}`).toBe(expected.includes(section));
          if (!expected.includes(section)) expect(refused()?.textContent).toMatch(/^You cannot manage .+ here\.$/);
          await mounted?.unmount();
          mounted = null;
        }
      });
    }
  }

  it('lists a page in the menus exactly when it would show, and no page an organization or a workspace lacks', () => {
    for (const caller of Object.keys(CALLERS)) {
      for (const [level] of SCOPES) {
        const access = answer(CALLERS[caller](level));
        expect(visibleSections(access, level).map((s) => s.id), `${caller} at ${level}`).toEqual(EXPECTED[caller][level]);
        expect(opensAccess(access, level), `${caller} at ${level}`).toBe(EXPECTED[caller][level].length > 0);
      }
    }
    // An `iam:` action no page lists opens nothing.
    expect(opensAccess({ actions: { 'iam:Unlisted': true } }, 'platform')).toBe(false);
    expect(LEVEL_SECTIONS.organization).toEqual(['policies', 'groups']);
    expect(LEVEL_SECTIONS.workspace).toEqual(['policies', 'groups']);
  });

  it('gives a delegated lister the policies to read, and no button to change them', async () => {
    const { api } = await render('delegated lister', wsScope, 'policies');
    expect(api.listPolicies).toHaveBeenCalledWith(undefined, 'abi:nexus:organization/acme/nexus:workspace/ws-1');
    expect(button('New policy')).toBeUndefined();
    expect(api.publishers).not.toHaveBeenCalled();
  });

  it('lets whoever may only create policies build one, without the list', async () => {
    const { api } = await render('policy builder', wsScope, 'policies');
    expect(api.listPolicies).not.toHaveBeenCalled();
    expect(mounted!.host.textContent).toContain('You may create policies here, not list them.');
    expect(button('New policy')).toBeDefined();
  });

  it('lets a workspace admin create groups and policies in their workspace, and nothing of the platform', async () => {
    await render('workspace admin', wsScope, 'groups');
    expect(button('Create group')).toBeDefined();
    await mounted?.unmount();
    await render('workspace admin', wsScope, 'policies');
    expect(button('New policy')).toBeDefined();
    await mounted?.unmount();
    await render('workspace admin', PLATFORM_ACCESS_SCOPE, 'policies');
    expect(refused()).not.toBeNull();
  });

  it('opens an organization to its admin, and tells the page when one of its workspaces is picked', async () => {
    const onPick = vi.fn();
    const { api } = await render('organization admin', orgScope, 'policies', { scopes: [orgScope, wsScope], onPick });
    expect(api.access).toHaveBeenLastCalledWith('abi:nexus:organization/acme');
    await mounted!.select(document.querySelector('[aria-label="Scope"]'), '1');
    expect(onPick).toHaveBeenCalledWith(1);
    await mounted?.unmount();
    const picked = await render('organization admin', orgScope, 'policies', { scopes: [orgScope, wsScope], picked: 1 });
    expect(picked.api.access).toHaveBeenLastCalledWith('abi:nexus:organization/acme/nexus:workspace/ws-1');
    expect(refused()).toBeNull();
  });

  it('opens the policy its address names, with who holds it', async () => {
    const listPolicies = vi.fn().mockResolvedValue({ items: [readerPolicy], next_after: null });
    const getPolicy = vi.fn().mockResolvedValue({ ...readerPolicy, sub_policies: [] });
    const validatePolicy = vi.fn().mockResolvedValue({ valid: true, errors: [], document: readerPolicy.document });
    const api = { ...apiFor('platform admin'), listPolicies, getPolicy, validatePolicy };
    await render('platform admin', PLATFORM_ACCESS_SCOPE, 'policies', { api, focus: 'pol_1' });
    await mounted!.flush();
    expect(document.querySelector('[aria-label="Policy Graph reader"]')).not.toBeNull();
    expect(document.querySelector('[aria-label="Who holds it"]')).not.toBeNull();
  });
});

describe('a person’s page', () => {
  const g = { id: 'grp_g', kind: 'group', status: 'active', name: 'G', email: null, display_name: null, provider: null, org: null, owner_id: null, created_at: null, owner_scope: 'abi:' };

  function personApi(caller: string, over: Record<string, unknown> = {}) {
    return {
      ...apiFor(caller),
      principalGroups: vi.fn().mockResolvedValue({ items: [g] }),
      getPrincipal: vi.fn().mockRejectedValue(new Error('no')),
      getGroup: vi.fn().mockResolvedValue({ ...g, members: [], idp_mappings: [] }),
      resources: vi.fn().mockResolvedValue({ items: [] }),
      ...over,
    } as ReturnType<typeof apiFor>;
  }

  it('shows what they hold and their groups, a group opening its page where Groups is shown', async () => {
    const api = personApi('platform admin');
    const navigate = vi.fn();
    mounted = await mount(PersonPage, {
      scope: PLATFORM_ACCESS_SCOPE,
      personId: 'usr_bob',
      navigate,
      groupHref: (id: string) => `/access/groups/${id}`,
      api,
      directory: fakeDirectory([]),
    });
    for (let i = 0; i < 3; i++) await mounted.flush();
    expect(document.querySelector('[data-person-page="usr_bob"]')).not.toBeNull();
    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: 'usr_bob' });
    await mounted.click(document.querySelector('[data-group-of="grp_g"] button'));
    expect(navigate).toHaveBeenCalledWith('/access/groups/grp_g');
  });

  it('links a group only where the caller is shown Groups', async () => {
    mounted = await mount(PersonPage, {
      scope: PLATFORM_ACCESS_SCOPE,
      personId: 'usr_bob',
      navigate: vi.fn(),
      groupHref: (id: string) => `/access/groups/${id}`,
      api: personApi('holdings lister'),
      directory: fakeDirectory([]),
    });
    for (let i = 0; i < 3; i++) await mounted.flush();
    expect(document.querySelector('[data-group-of="grp_g"]')?.textContent).toContain('G');
    expect(document.querySelector('[data-group-of="grp_g"] button')).toBeNull();
  });

  describe('an account linked from the old login', () => {
    const WS1 = 'abi:nexus:organization/acme/nexus:workspace/ws-1';
    // IAM knows Bob as usr_bob; ws-1's members, as user-7 (his account of the old login).
    const bob = { id: 'usr_bob', kind: 'user', status: 'active', name: null, email: 'bob@example.com', display_name: 'Bob', provider: null, org: null, owner_id: null, created_at: null };
    const wg = { ...bob, id: 'grp_g', kind: 'group', name: 'G', email: null, display_name: null, owner_scope: WS1 };
    const role = { id: 'a_w', policy_id: 'builtin.member', policy_name: 'Member', policy_owner_scope: 'abi:', principal_id: 'usr_bob', principal: bob, scope: WS1, created_at: null };
    const members = fakeDirectory([{ userId: 'user-7', name: 'Bob', email: 'bob@example.com', role: 'member', inherited: false }]);
    const linkedWorld = () =>
      personApi('workspace admin', {
        listAttachments: vi.fn(({ principal_id }: { principal_id?: string } = {}) =>
          Promise.resolve({ items: principal_id === 'usr_bob' ? [role] : [] }),
        ),
        principalGroups: vi.fn().mockResolvedValue({ items: [wg] }),
        getGroup: vi.fn().mockResolvedValue({ ...wg, members: [bob], idp_mappings: [] }),
        listGroups: vi.fn().mockResolvedValue({ items: [wg] }),
      });

    it('changes his role as the members name him, on his page under Members', async () => {
      const changeRole = vi.fn().mockResolvedValue(undefined);
      mounted = await mount(PersonPage, {
        scope: wsScope,
        personId: 'usr_bob',
        navigate: vi.fn(),
        groupHref: null,
        api: linkedWorld(),
        directory: members,
        changeRole,
      });
      for (let i = 0; i < 4; i++) await mounted.flush();
      await mounted.select(document.querySelector('[aria-label="Role at Workspace ws-1 (acme)"]'), 'viewer');
      expect(changeRole).toHaveBeenCalledWith({ level: 'workspace', workspaceId: 'ws-1' }, 'user-7', 'viewer');
    });

    it('opens his page from a group’s members', async () => {
      const navigate = vi.fn();
      mounted = await mount(AccessPage, {
        section: 'groups',
        scopes: [wsScope],
        focus: 'grp_g',
        api: linkedWorld(),
        directory: members,
        hrefs,
        navigate,
      });
      for (let i = 0; i < 4; i++) await mounted.flush();
      await mounted.click(document.querySelector('[aria-label="Open Bob"]'));
      expect(navigate).toHaveBeenCalledWith('/people/usr_bob');
    });
  });
});
