// @vitest-environment jsdom
/**
 * Permission profiles: the one Roles & permissions UI rendered at the platform, an
 * organization and a workspace, for each kind of caller. What each caller holds is what
 * `GET /api/iam/admin/access?scope=` answers them (the API's tests check those answers); the
 * UI shows exactly the sections and buttons those actions allow, nothing per level.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AccessView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { fakeApi, fakeDirectory, orgScope, readerPolicy, wsScope } from './access-fixtures';
import { PLATFORM_ACCESS_SCOPE, type AccessScope } from './access-scope';
import { ACCESS_SECTIONS, opensRolesAndPermissions, parseAccessSection } from './access-sections';
import { RolesAndPermissions } from './roles-and-permissions';

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

type Level = 'platform' | 'org' | 'ws';
const levelOf = (scope?: string): Level => (scope === undefined ? 'platform' : scope.includes('/nexus:workspace/') ? 'ws' : 'org');

/** What each caller holds, by level, as the API answers `access`. */
const CALLERS: Record<string, (level: Level) => string[]> = {
  'platform admin': (level) =>
    level === 'platform' ? [...LEVEL, ...PLATFORM_ONLY] : LEVEL,
  'organization admin': (level) => (level === 'org' || level === 'ws' ? LEVEL : []),
  'workspace admin': (level) => (level === 'ws' ? LEVEL : []),
  'delegated lister': () => ['iam:ListPolicies'],
  // May create policies, not list them: builds one from what it holds.
  'policy builder': () => ['iam:CreatePolicy'],
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
    publishers: vi.fn().mockResolvedValue({ scope: '', publishers: [] }),
  });
}

async function render(caller: string, scope: AccessScope) {
  const api = apiFor(caller);
  mounted = await mount(RolesAndPermissions, { scopes: [scope], api, directory: fakeDirectory([]) });
  await mounted.flush();
  await mounted.flush();
  return api;
}

const sections = () => [...document.querySelectorAll('[data-section]')].map((b) => b.getAttribute('data-section'));
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const nothing = () => document.querySelector('[role="status"]')?.textContent;

const SCOPES: [string, AccessScope, string | undefined][] = [
  ['the platform', PLATFORM_ACCESS_SCOPE, undefined],
  ['an organization', orgScope, 'abi:nexus:organization/acme'],
  ['a workspace', wsScope, 'abi:nexus:organization/acme/nexus:workspace/ws-1'],
];

const EXPECTED: Record<string, Record<string, string[]>> = {
  'platform admin': {
    'the platform': ['people', 'groups', 'policies', 'service-accounts', 'approvals', 'simulator', 'audit'],
    'an organization': ['people', 'groups', 'policies'],
    'a workspace': ['people', 'groups', 'policies'],
  },
  'organization admin': {
    'the platform': [],
    'an organization': ['people', 'groups', 'policies'],
    'a workspace': ['people', 'groups', 'policies'],
  },
  'workspace admin': { 'the platform': [], 'an organization': [], 'a workspace': ['people', 'groups', 'policies'] },
  'delegated lister': { 'the platform': ['policies'], 'an organization': ['policies'], 'a workspace': ['policies'] },
  'policy builder': { 'the platform': ['policies'], 'an organization': ['policies'], 'a workspace': ['policies'] },
  viewer: { 'the platform': [], 'an organization': [], 'a workspace': [] },
  stranger: { 'the platform': [], 'an organization': [], 'a workspace': [] },
};

const WHERE: Record<Level, string> = { platform: 'the platform', org: 'an organization', ws: 'a workspace' };
const EXPECTED_ANY = (caller: string, level: Level) => EXPECTED[caller][WHERE[level]].length > 0;

describe('Roles & permissions, one UI for every level', () => {
  for (const caller of Object.keys(CALLERS)) {
    for (const [where, scope, asked] of SCOPES) {
      const expected = EXPECTED[caller][where];
      it(`shows ${caller} at ${where} ${expected.length ? expected.join(', ') : 'nothing'}`, async () => {
        const api = await render(caller, scope);
        expect(api.access).toHaveBeenCalledWith(asked);
        expect(sections()).toEqual(expected);
        if (!expected.length) expect(nothing()).toBe('You cannot manage roles or permissions here.');
      });
    }
  }

  it('shows the menu item exactly when the page would show a section', () => {
    for (const caller of Object.keys(CALLERS)) {
      for (const level of ['platform', 'org', 'ws'] as const) {
        const access = answer(CALLERS[caller](level));
        expect(opensRolesAndPermissions(access), `${caller} at ${level}`).toBe(EXPECTED_ANY(caller, level));
      }
    }
    // An `iam:` action no section lists opens nothing.
    expect(opensRolesAndPermissions({ actions: { 'iam:Unlisted': true } })).toBe(false);
  });

  it('gives a delegated lister the policies to read, and no button to change them', async () => {
    const api = await render('delegated lister', wsScope);
    expect(api.listPolicies).toHaveBeenCalledWith(undefined, 'abi:nexus:organization/acme/nexus:workspace/ws-1');
    expect(button('New policy')).toBeUndefined();
    expect(api.publishers).not.toHaveBeenCalled();
  });

  it('lets whoever may only create policies build one, without the list', async () => {
    const api = await render('policy builder', wsScope);
    expect(api.listPolicies).not.toHaveBeenCalled();
    expect(mounted!.host.textContent).toContain('You may create policies here, not list them.');
    expect(button('New policy')).toBeDefined();
  });

  it('lets a workspace admin create groups and policies in their workspace, and nothing of the platform', async () => {
    await render('workspace admin', wsScope);
    await mounted!.click(document.querySelector('[data-section="groups"]'));
    await mounted!.flush();
    expect(button('Create group')).toBeDefined();
    await mounted!.click(document.querySelector('[data-section="policies"]'));
    await mounted!.flush();
    expect(button('New policy')).toBeDefined();
    expect(sections()).not.toContain('service-accounts');
  });

  it('has no built-in roles section: features come from policies, like agents', () => {
    expect(ACCESS_SECTIONS.map((s) => s.label)).not.toContain('Built-in roles');
    // A section that no longer exists opens the first one the caller may.
    expect(parseAccessSection('gone', answer(LEVEL))).toBe('people');
  });

  it('opens an organization to its admin, and switches to one of its workspaces', async () => {
    const api = apiFor('organization admin');
    mounted = await mount(RolesAndPermissions, { scopes: [orgScope, wsScope], api, directory: fakeDirectory([]) });
    await mounted.flush();
    expect(sections()).toEqual(['people', 'groups', 'policies']);

    const picker = document.querySelector('[aria-label="Scope"]') as HTMLSelectElement;
    picker.value = '1';
    picker.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted.flush();
    await mounted.flush();
    expect(api.access).toHaveBeenLastCalledWith('abi:nexus:organization/acme/nexus:workspace/ws-1');
    expect(sections()).toEqual(['people', 'groups', 'policies']);
  });
});

describe('Roles & permissions opened from a link', () => {
  afterEach(() => window.history.replaceState({}, '', '/'));

  it('opens the section and the policy the address names', async () => {
    window.history.replaceState({}, '', '/settings/roles?section=policies&policy=pol_1');
    const api = apiFor('platform admin');
    (api as unknown as Record<string, unknown>).listPolicies = vi.fn().mockResolvedValue({ items: [readerPolicy], next_after: null });
    mounted = await mount(RolesAndPermissions, { scopes: [PLATFORM_ACCESS_SCOPE], api, directory: fakeDirectory([]) });
    await mounted.flush();
    await mounted.flush();
    expect(document.querySelector('[data-section="policies"]')?.getAttribute('aria-current')).toBe('page');
    expect(document.querySelector('[aria-label="Policy Graph reader"]')).not.toBeNull();
  });

  function linkedApi() {
    const api = apiFor('platform admin') as unknown as Record<string, unknown>;
    const g = { id: 'grp_g', kind: 'group', status: 'active', name: 'G', email: null, display_name: null, provider: null, org: null, owner_id: null, created_at: null, owner_scope: 'abi:' };
    Object.assign(api, {
      principalGroups: vi.fn().mockResolvedValue({ items: [g] }),
      getPrincipal: vi.fn().mockRejectedValue(new Error('no')),
      getGroup: vi.fn().mockResolvedValue({ ...g, members: [], idp_mappings: [] }),
      resources: vi.fn().mockResolvedValue({ items: [] }),
    });
    return api as unknown as ReturnType<typeof apiFor>;
  }

  it('opens a person’s page the address names, and their group’s page from it', async () => {
    window.history.replaceState({}, '', '/settings/roles?section=people&person=usr_bob');
    const api = linkedApi();
    mounted = await mount(RolesAndPermissions, { scopes: [PLATFORM_ACCESS_SCOPE], api, directory: fakeDirectory([]) });
    await mounted.flush();
    await mounted.flush();
    expect(document.querySelector('[data-person-page="usr_bob"]')).not.toBeNull();
    expect(api.listAttachments).toHaveBeenCalledWith({ principal_id: 'usr_bob' });

    await mounted.click(document.querySelector('[data-group-of="grp_g"] button'));
    await mounted.flush();
    expect(document.querySelector('[data-section="groups"]')?.getAttribute('aria-current')).toBe('page');
    expect(document.querySelector('[data-group-detail="grp_g"]')).not.toBeNull();
    expect(window.location.search).toBe('?section=groups&group=grp_g');

    // A section's tab closes the page, and the address follows.
    await mounted.click(document.querySelector('[data-section="people"]'));
    await mounted.flush();
    expect(document.querySelector('[data-person-page]')).toBeNull();
    expect(window.location.search).toBe('?section=people');
  });

  describe('an account linked from the old login', () => {
    const WS1 = 'abi:nexus:organization/acme/nexus:workspace/ws-1';
    // IAM knows Bob as usr_bob; ws-1's members, as user-7 (his account of the old login).
    const bob = { id: 'usr_bob', kind: 'user', status: 'active', name: null, email: 'bob@example.com', display_name: 'Bob', provider: null, org: null, owner_id: null, created_at: null };
    const g = { ...bob, id: 'grp_g', kind: 'group', name: 'G', email: null, display_name: null, owner_scope: WS1 };
    const role = { id: 'a_w', policy_id: 'builtin.member', policy_name: 'Member', policy_owner_scope: 'abi:', principal_id: 'usr_bob', principal: bob, scope: WS1, created_at: null };
    const members = fakeDirectory([{ userId: 'user-7', name: 'Bob', email: 'bob@example.com', role: 'member', inherited: false }]);

    function linkedWorld() {
      const api = apiFor('workspace admin') as unknown as Record<string, unknown>;
      Object.assign(api, {
        listAttachments: vi.fn(({ principal_id }: { principal_id?: string } = {}) =>
          Promise.resolve({ items: principal_id === 'usr_bob' ? [role] : [] }),
        ),
        principalGroups: vi.fn().mockResolvedValue({ items: [g] }),
        getPrincipal: vi.fn().mockRejectedValue(new Error('no')),
        getGroup: vi.fn().mockResolvedValue({ ...g, members: [bob], idp_mappings: [] }),
        listGroups: vi.fn().mockResolvedValue({ items: [g] }),
        resources: vi.fn().mockResolvedValue({ items: [] }),
      });
      return api as unknown as ReturnType<typeof apiFor>;
    }

    async function changeAt(start: string, changeRole: ReturnType<typeof vi.fn>) {
      window.history.replaceState({}, '', start);
      mounted = await mount(RolesAndPermissions, { scopes: [wsScope], api: linkedWorld(), directory: members, changeRole });
      for (let i = 0; i < 4; i++) await mounted.flush();
    }

    it('changes his role as the members name him, opened by URL', async () => {
      const changeRole = vi.fn().mockResolvedValue(undefined);
      await changeAt('/workspace/ws-1/settings/permissions?section=people&person=usr_bob', changeRole);
      await mounted!.select(document.querySelector('[aria-label="Role at Workspace ws-1 (acme)"]'), 'viewer');
      expect(changeRole).toHaveBeenCalledWith({ level: 'workspace', workspaceId: 'ws-1' }, 'user-7', 'viewer');
    });

    it('changes his role as the members name him, opened from a group’s members', async () => {
      const changeRole = vi.fn().mockResolvedValue(undefined);
      await changeAt('/workspace/ws-1/settings/permissions?section=groups&group=grp_g', changeRole);
      await mounted!.click(document.querySelector('[aria-label="Open Bob"]'));
      for (let i = 0; i < 4; i++) await mounted!.flush();
      expect(document.querySelector('[data-person-page="usr_bob"]')).not.toBeNull();
      await mounted!.select(document.querySelector('[aria-label="Role at Workspace ws-1 (acme)"]'), 'viewer');
      expect(changeRole).toHaveBeenCalledWith({ level: 'workspace', workspaceId: 'ws-1' }, 'user-7', 'viewer');
    });
  });

  it('closes the open page when the scope changes, and the address follows', async () => {
    window.history.replaceState({}, '', '/organizations/acme/settings/roles?section=groups&group=grp_g');
    const api = linkedApi();
    mounted = await mount(RolesAndPermissions, { scopes: [orgScope, wsScope], api, directory: fakeDirectory([]) });
    await mounted.flush();
    await mounted.flush();
    expect(document.querySelector('[data-group-detail="grp_g"]')).not.toBeNull();
    await mounted.select(document.querySelector('[aria-label="Scope"]'), '1');
    await mounted.flush();
    await mounted.flush();
    expect(document.querySelector('[data-group-detail]')).toBeNull();
    expect(window.location.search).toBe('?section=groups');
  });

  it('links a group only where the caller is shown Groups', async () => {
    window.history.replaceState({}, '', '/settings/roles?section=people&person=usr_bob');
    const api = linkedApi() as unknown as Record<string, unknown>;
    // May list attachments, not groups: People & roles alone.
    api.access = vi.fn(() => Promise.resolve(answer(['iam:ListAttachments'])));
    mounted = await mount(RolesAndPermissions, { scopes: [PLATFORM_ACCESS_SCOPE], api: api as never, directory: fakeDirectory([]) });
    await mounted.flush();
    await mounted.flush();
    expect(sections()).toEqual(['people']);
    expect(document.querySelector('[data-group-of="grp_g"]')?.textContent).toContain('G');
    expect(document.querySelector('[data-group-of="grp_g"] button')).toBeNull();
  });
});

