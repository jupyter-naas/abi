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
import { catalogsView, fakeApi, fakeDirectory, orgScope, wsScope } from './access-fixtures';
import { PLATFORM_ACCESS_SCOPE, type AccessScope } from './access-scope';
import { opensRolesAndPermissions } from './access-sections';
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
  'iam:GetSet',
  'iam:PutSet',
  'nexus:ReadSystem',
];
const ROLE_FEATURES = ['nexus:GetRoleFeatures', 'nexus:UpdateRoleFeatures'];

type Level = 'platform' | 'org' | 'ws';
const levelOf = (scope?: string): Level => (scope === undefined ? 'platform' : scope.endsWith(':-') ? 'org' : 'ws');

/** What each caller holds, by level, as the API answers `access`. */
const CALLERS: Record<string, (level: Level) => string[]> = {
  'platform admin': (level) =>
    level === 'platform' ? [...LEVEL, ...PLATFORM_ONLY] : level === 'org' ? [...LEVEL, ...ROLE_FEATURES] : LEVEL,
  'organization admin': (level) => (level === 'org' ? [...LEVEL, ...ROLE_FEATURES] : level === 'ws' ? LEVEL : []),
  'workspace admin': (level) => (level === 'ws' ? LEVEL : []),
  'delegated lister': () => ['iam:ListPolicies'],
  viewer: () => [],
  stranger: () => [],
};

function answer(holds: string[]): AccessView {
  const all = [...LEVEL, ...PLATFORM_ONLY, ...ROLE_FEATURES];
  return { actions: Object.fromEntries(all.map((a) => [a, holds.includes(a)])) };
}

function apiFor(caller: string) {
  return fakeApi({
    access: vi.fn((scope?: string) => Promise.resolve(answer(CALLERS[caller](levelOf(scope))))),
    listAttachments: vi.fn().mockResolvedValue({ items: [] }),
    attachable: vi.fn().mockResolvedValue({ items: [] }),
    listGroups: vi.fn().mockResolvedValue({ items: [] }),
    listPolicies: vi.fn().mockResolvedValue({ items: [], next_after: null }),
    catalogs: vi.fn().mockResolvedValue(catalogsView),
    grantable: vi.fn().mockResolvedValue({ scope: '', catalogs: [] }),
    moduleScopes: vi.fn().mockResolvedValue({ modules: [] }),
  });
}

const roleFeatures = {
  read: vi.fn().mockResolvedValue({ enabled_features: ['chat'], known_features: [], roles: ['owner', 'admin', 'member', 'viewer'], role_baseline: {} }),
  save: vi.fn(),
};

async function render(caller: string, scope: AccessScope) {
  const api = apiFor(caller);
  mounted = await mount(RolesAndPermissions, { scopes: [scope], api, directory: fakeDirectory([]), roleFeatures });
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
  ['an organization', orgScope, 'abi:acme:-'],
  ['a workspace', wsScope, 'abi:acme:ws-1'],
];

const EXPECTED: Record<string, Record<string, string[]>> = {
  'platform admin': {
    'the platform': ['people', 'groups', 'policies', 'service-accounts', 'approvals', 'simulator', 'audit'],
    'an organization': ['people', 'groups', 'policies', 'role-features'],
    'a workspace': ['people', 'groups', 'policies'],
  },
  'organization admin': {
    'the platform': [],
    'an organization': ['people', 'groups', 'policies', 'role-features'],
    'a workspace': ['people', 'groups', 'policies'],
  },
  'workspace admin': { 'the platform': [], 'an organization': [], 'a workspace': ['people', 'groups', 'policies'] },
  'delegated lister': { 'the platform': ['policies'], 'an organization': ['policies'], 'a workspace': ['policies'] },
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
    // An `iam:` action no section lists (the sets page's) opens nothing; an org's role
    // feature defaults alone open Built-in roles.
    expect(opensRolesAndPermissions({ actions: { 'iam:GetSet': true } })).toBe(false);
    expect(opensRolesAndPermissions({ actions: { 'nexus:GetRoleFeatures': true } })).toBe(true);
  });

  it('gives a delegated lister the policies to read, and no button to change them', async () => {
    const api = await render('delegated lister', wsScope);
    expect(api.listPolicies).toHaveBeenCalledWith(undefined, 'abi:acme:ws-1');
    expect(button('New policy')).toBeUndefined();
    expect(api.grantable).not.toHaveBeenCalled();
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

  it('opens an organization’s built-in roles to its admin, and switches to one of its workspaces', async () => {
    const api = apiFor('organization admin');
    mounted = await mount(RolesAndPermissions, { scopes: [orgScope, wsScope], api, directory: fakeDirectory([]), roleFeatures });
    await mounted.flush();
    await mounted.click(document.querySelector('[data-section="role-features"]'));
    await mounted.flush();
    expect(roleFeatures.read).toHaveBeenCalledWith('acme');
    expect(document.querySelector('[aria-label="Member can use Chat"]')).not.toBeNull();

    const picker = document.querySelector('[aria-label="Scope"]') as HTMLSelectElement;
    picker.value = '1';
    picker.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted.flush();
    await mounted.flush();
    expect(api.access).toHaveBeenLastCalledWith('abi:acme:ws-1');
    expect(sections()).toEqual(['people', 'groups', 'policies']);
  });
});
