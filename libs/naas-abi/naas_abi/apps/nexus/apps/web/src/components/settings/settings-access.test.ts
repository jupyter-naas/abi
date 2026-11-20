// @vitest-environment jsdom
import { createElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

/**
 * Who sees what in Settings and the Console: each person as the API answers them (their
 * roles, then what IAM grants them on the platform, an organization and the workspace),
 * read by the hooks the shell uses. Only the network is a fake.
 */

type Scope = 'platform' | 'workspace' | `organization:${string}`;

type Person = {
  id: string;
  workspaceRole: 'owner' | 'admin' | 'member' | 'viewer';
  organizations: { id: string; name: string; role: 'owner' | 'admin' | 'member' }[];
  grants: Partial<Record<Scope, string[]>>;
};

const world = vi.hoisted(() => ({ person: null as Person | null }));

vi.mock('@/stores/auth', async (importOriginal) => {
  const ORGANIZATION = 'abi:nexus:organization/';
  const WORKSPACE = `${ORGANIZATION}acme/nexus:workspace/ws-1`;
  const json = (body: unknown) =>
    new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
  const scopeOf = (asked: string | null): Scope | null => {
    if (asked === null) return 'platform';
    if (asked === WORKSPACE) return 'workspace';
    return asked.startsWith(ORGANIZATION) && !asked.includes('/nexus:')
      ? `organization:${asked.slice(ORGANIZATION.length)}`
      : null;
  };
  return {
    ...(await importOriginal<typeof import('@/stores/auth')>()),
    useAuthStore: (select: (s: unknown) => unknown) => select({ user: { id: world.person?.id ?? 'nobody' } }),
    authFetch: async (input: string) => {
      const person = world.person;
      const url = new URL(input, 'http://nexus.test');
      if (!person) return new Response(null, { status: 401 });
      if (url.pathname === '/api/organizations') {
        return json(person.organizations.map((o) => ({ id: o.id, name: o.name, current_user_role: o.role })));
      }
      if (url.pathname === '/api/iam/admin/access') {
        const scope = scopeOf(url.searchParams.get('scope'));
        const granted = (scope && person.grants[scope]) || [];
        return json({ actions: Object.fromEntries(granted.map((action) => [action, true])) });
      }
      return new Response(null, { status: 404 });
    },
  };
});
vi.mock('@/hooks/use-workspace-resources', () => ({ useWorkspaceResources: () => ({ resources: null }) }));

import { useWorkspaceStore } from '@/stores/workspace';
import { useSettingsLevels } from '@/hooks/use-settings-levels';
import { useAvatarSettingsLinks } from '@/hooks/use-avatar-settings-links';

type Seen = { levels: Record<string, string[]>; settings: string; console: string | null };

function Probe() {
  const levels = useSettingsLevels();
  const { settings, console: consoleEntry } = useAvatarSettingsLinks();
  const seen: Seen = {
    levels: Object.fromEntries(
      levels.map((level) => [level.label, level.groups.flatMap((group) => group.links.map((link) => link.label))])
    ),
    settings: settings.href,
    console: consoleEntry === null ? null : consoleEntry === 'loading' ? 'loading' : consoleEntry.href,
  };
  return createElement('pre', null, JSON.stringify(seen));
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  world.person = null;
  window.sessionStorage.clear();
});

async function seenBy(person: Person): Promise<Seen> {
  world.person = person;
  useWorkspaceStore.setState({
    workspaces: [{ id: 'ws-1', name: 'Ops', organizationId: 'acme', currentUserRole: person.workspaceRole }] as never,
    currentWorkspaceId: 'ws-1',
  });
  mounted = await mount(Probe, {});
  for (let i = 0; i < 4; i += 1) await mounted.flush();
  return JSON.parse(mounted.host.textContent ?? '{}') as Seen;
}

const ACME = { id: 'acme', name: 'Acme' };
const ALL_PLATFORM = ['nexus:ReadSystem', 'nexus:ListUsers', 'nexus:ListDrives', 'iam:ListAttachments'];

describe('who sees what in Settings and the Console', () => {
  it('a platform admin: every level, and the Console', async () => {
    const seen = await seenBy({
      id: 'root',
      workspaceRole: 'owner',
      organizations: [{ ...ACME, role: 'owner' }],
      grants: { platform: ALL_PLATFORM, workspace: ['iam:ListAttachments'], 'organization:acme': ['iam:ListAttachments'] },
    });
    expect(Object.keys(seen.levels)).toEqual(['Account', 'Workspace', 'Organization', 'Platform']);
    expect(seen.levels.Platform).toEqual(['General', 'Organizations', 'Users', 'Roles & permissions', 'Drives']);
    expect(seen.settings).toBe('/workspace/ws-1/settings/general');
    expect(seen.console).toBe('/settings/system');
  });

  it('an organization admin: their workspace and organization, nothing of the platform', async () => {
    const seen = await seenBy({
      id: 'olivia',
      workspaceRole: 'admin',
      organizations: [{ ...ACME, role: 'admin' }],
      grants: { workspace: ['iam:ListAttachments'], 'organization:acme': ['iam:ListAttachments'] },
    });
    expect(Object.keys(seen.levels)).toEqual(['Account', 'Workspace', 'Organization']);
    expect(seen.levels.Organization).toEqual(['General', 'Branding', 'Workspaces', 'Members', 'Roles & permissions']);
    expect(seen.levels.Workspace).toContain('Roles & permissions');
    expect(seen.console).toBeNull();
  });

  it('a workspace owner who is a member of the organization: no Organization level', async () => {
    const seen = await seenBy({
      id: 'bob',
      workspaceRole: 'owner',
      organizations: [{ ...ACME, role: 'member' }],
      grants: { workspace: ['iam:ListAttachments'] },
    });
    expect(Object.keys(seen.levels)).toEqual(['Account', 'Workspace']);
    expect(seen.levels.Workspace).toEqual(expect.arrayContaining(['General', 'Members', 'Roles & permissions']));
    expect(seen.settings).toBe('/workspace/ws-1/settings/general');
  });

  it('a workspace owner IAM gives no right over access: the workspace without Roles & permissions', async () => {
    const seen = await seenBy({
      id: 'otto',
      workspaceRole: 'owner',
      organizations: [{ ...ACME, role: 'member' }],
      grants: {},
    });
    expect(seen.levels.Workspace).toContain('General');
    expect(seen.levels.Workspace).not.toContain('Roles & permissions');
  });

  it('a member to whom IAM delegates the workspace\'s access: Roles & permissions alone', async () => {
    const seen = await seenBy({
      id: 'carol',
      workspaceRole: 'member',
      organizations: [{ ...ACME, role: 'member' }],
      grants: { workspace: ['iam:ListPolicies'] },
    });
    expect(seen.levels).toEqual({
      Account: ['Profile', 'Appearance'],
      Workspace: ['Roles & permissions'],
    });
    expect(seen.settings).toBe('/workspace/ws-1/settings/permissions');
  });

  it('a plain member: their account alone, and Settings opens it', async () => {
    const seen = await seenBy({
      id: 'dave',
      workspaceRole: 'member',
      organizations: [{ ...ACME, role: 'member' }],
      grants: {},
    });
    expect(seen).toEqual({ levels: { Account: ['Profile', 'Appearance'] }, settings: '/account/profile', console: null });
  });

  it('a viewer: the same as a member', async () => {
    const seen = await seenBy({ id: 'vera', workspaceRole: 'viewer', organizations: [], grants: {} });
    expect(seen).toEqual({ levels: { Account: ['Profile', 'Appearance'] }, settings: '/account/profile', console: null });
  });

  it('a member to whom IAM delegates the organization\'s access: its Roles & permissions alone', async () => {
    const seen = await seenBy({
      id: 'eve',
      workspaceRole: 'member',
      organizations: [{ ...ACME, role: 'member' }],
      grants: { 'organization:acme': ['iam:ListAttachments'] },
    });
    expect(seen.levels).toEqual({ Account: ['Profile', 'Appearance'], Organization: ['Roles & permissions'] });
  });

  it('the admin of another organization than the workspace\'s: that one, named', async () => {
    const seen = await seenBy({
      id: 'nina',
      workspaceRole: 'member',
      organizations: [
        { ...ACME, role: 'member' },
        { id: 'beta', name: 'Beta', role: 'admin' },
      ],
      grants: { 'organization:beta': [] },
    });
    expect(Object.keys(seen.levels)).toEqual(['Account', 'Organization · Beta']);
    expect(seen.levels['Organization · Beta']).toContain('Members');
  });

  it('someone who may read the system: General and Organizations, and the Console', async () => {
    const seen = await seenBy({
      id: 'sam',
      workspaceRole: 'member',
      organizations: [],
      grants: { platform: ['nexus:ReadSystem'] },
    });
    expect(seen.levels).toEqual({ Account: ['Profile', 'Appearance'], Platform: ['General', 'Organizations'] });
    expect(seen.console).toBe('/settings/system');
  });

  it('someone who may list the users only: Users, and no Console', async () => {
    const seen = await seenBy({
      id: 'uma',
      workspaceRole: 'member',
      organizations: [],
      grants: { platform: ['nexus:ListUsers'] },
    });
    expect(seen.levels).toEqual({ Account: ['Profile', 'Appearance'], Platform: ['Users'] });
    expect(seen.console).toBeNull();
  });
});
