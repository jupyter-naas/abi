// @vitest-environment jsdom
import { createElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

/**
 * Who sees what in Settings: each person as the API answers them (their roles, then what
 * IAM grants them on the platform, an organization and the workspace), read by the hooks
 * the shell uses. Only the network is a fake.
 */

type Scope = 'platform' | 'workspace' | `organization:${string}`;

type Person = {
  id: string;
  workspaceRole: 'owner' | 'admin' | 'member' | 'viewer';
  organizations: { id: string; name: string; role: 'owner' | 'admin' | 'member' }[];
  grants: Partial<Record<Scope, string[]>>;
};

const world = vi.hoisted(() => ({ person: null as Person | null, path: '' }));

vi.mock('next/navigation', () => ({ usePathname: () => world.path }));
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
import { useSettingsTabs } from '@/hooks/use-settings-levels';
import { useSettingsHref } from '@/hooks/use-avatar-settings-links';

/**
 * `tabs`: their labels, none with one level; `opens`: where each tab leads. `level`: the
 * level the column lists on this page, and `column` its groups, each under its heading
 * (the level's own for its first group).
 */
type Seen = {
  settings: string;
  tabs: string[];
  opens: Record<string, string>;
  level: string | null;
  column: Record<string, string[]>;
};

function Probe() {
  const { tabs, level } = useSettingsTabs({ mobile: false });
  const settings = useSettingsHref();
  const seen: Seen = {
    settings,
    tabs: tabs.map((tab) => tab.label),
    opens: Object.fromEntries(tabs.map((tab) => [tab.label, tab.href])),
    level: level?.label ?? null,
    column: Object.fromEntries(
      (level?.groups ?? []).map((group) => [group.label ?? level?.label, group.links.map((link) => link.label)])
    ),
  };
  return createElement('pre', null, JSON.stringify(seen));
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  world.person = null;
  world.path = '';
  window.sessionStorage.clear();
});

async function probe(): Promise<Seen> {
  await mounted?.unmount();
  mounted = await mount(Probe, {});
  for (let i = 0; i < 4; i += 1) await mounted.flush();
  return JSON.parse(mounted.host.textContent ?? '{}') as Seen;
}

/** What ``person`` sees on ``path``; by default where Settings opens for them. */
async function seenBy(person: Person, path?: string): Promise<Seen> {
  world.person = person;
  useWorkspaceStore.setState({
    workspaces: [{ id: 'ws-1', name: 'Ops', organizationId: 'acme', currentUserRole: person.workspaceRole }] as never,
    currentWorkspaceId: 'ws-1',
  });
  world.path = path ?? '';
  const seen = await probe();
  if (path !== undefined) return seen;
  world.path = seen.settings;
  return probe();
}

const ACME = { id: 'acme', name: 'Acme' };
const ALL_PLATFORM = ['nexus:ReadSystem', 'nexus:ListUsers', 'nexus:ListDrives', 'iam:ListAttachments'];
const PLATFORM_GROUPS = ['Administration', 'System', 'Activity', 'Resources', 'Data'];

describe('who sees what in Settings', () => {
  it('a platform admin: the four tabs, Settings opening on the workspace, the Platform tab with every group', async () => {
    const root: Person = {
      id: 'root',
      workspaceRole: 'owner',
      organizations: [{ ...ACME, role: 'owner' }],
      grants: { platform: ALL_PLATFORM, workspace: ['iam:ListAttachments'], 'organization:acme': ['iam:ListAttachments'] },
    };
    const seen = await seenBy(root);
    expect(seen.tabs).toEqual(['Platform', 'Organization', 'Workspace', 'Account']);
    expect(seen.settings).toBe('/workspace/ws-1/settings/general');
    expect(seen.level).toBe('Workspace');
    expect(Object.keys(seen.column)).toEqual(['Workspace', 'Features']);
    expect(seen.column.Workspace).toEqual(expect.arrayContaining(['General', 'Members', 'Roles & permissions']));

    const platform = await seenBy(root, seen.opens.Platform);
    expect(seen.opens.Platform).toBe('/settings/general');
    expect(platform.level).toBe('Platform');
    expect(Object.keys(platform.column)).toEqual(PLATFORM_GROUPS);
    expect(platform.column.Administration).toEqual(['General', 'Organizations', 'Users', 'Roles & permissions', 'Drives']);
    expect(platform.column.System).toEqual(expect.arrayContaining(['Overview', 'Jobs', 'Layers', 'Diagrams']));
  });

  it('an organization admin: their organization and workspace, no Platform tab', async () => {
    const olivia: Person = {
      id: 'olivia',
      workspaceRole: 'admin',
      organizations: [{ ...ACME, role: 'admin' }],
      grants: { workspace: ['iam:ListAttachments'], 'organization:acme': ['iam:ListAttachments'] },
    };
    const seen = await seenBy(olivia);
    expect(seen.tabs).toEqual(['Organization', 'Workspace', 'Account']);
    expect(seen.column.Workspace).toContain('Roles & permissions');
    const organization = await seenBy(olivia, seen.opens.Organization);
    expect(organization.level).toBe('Organization');
    expect(organization.column).toEqual({
      Organization: ['General', 'Branding', 'Workspaces', 'Members', 'Roles & permissions'],
    });
  });

  it('a workspace owner who is a member of the organization: no Organization tab', async () => {
    const seen = await seenBy({
      id: 'bob',
      workspaceRole: 'owner',
      organizations: [{ ...ACME, role: 'member' }],
      grants: { workspace: ['iam:ListAttachments'] },
    });
    expect(seen.tabs).toEqual(['Workspace', 'Account']);
    expect(seen.settings).toBe('/workspace/ws-1/settings/general');
    expect(seen.column.Workspace).toEqual(expect.arrayContaining(['General', 'Members', 'Roles & permissions']));
  });

  it('a workspace owner IAM gives no right over access: the workspace without Roles & permissions', async () => {
    const seen = await seenBy({
      id: 'otto',
      workspaceRole: 'owner',
      organizations: [{ ...ACME, role: 'member' }],
      grants: {},
    });
    expect(seen.level).toBe('Workspace');
    expect(seen.column.Workspace).toContain('General');
    expect(seen.column.Workspace).not.toContain('Roles & permissions');
  });

  it('a member to whom IAM delegates the workspace\'s access: Roles & permissions alone', async () => {
    const seen = await seenBy({
      id: 'carol',
      workspaceRole: 'member',
      organizations: [{ ...ACME, role: 'member' }],
      grants: { workspace: ['iam:ListPolicies'] },
    });
    expect(seen.tabs).toEqual(['Workspace', 'Account']);
    expect(seen.settings).toBe('/workspace/ws-1/settings/permissions');
    expect(seen.column).toEqual({ Workspace: ['Roles & permissions'] });
  });

  it('a plain member: no tabs, their account alone, and Settings opens it', async () => {
    const dave: Person = {
      id: 'dave',
      workspaceRole: 'member',
      organizations: [{ ...ACME, role: 'member' }],
      grants: {},
    };
    const expected: Seen = {
      settings: '/account/profile',
      tabs: [],
      opens: {},
      level: 'Account',
      column: { Account: ['Profile', 'Appearance'] },
    };
    expect(await seenBy(dave)).toEqual(expected);
    // A page they may not open: the layout refuses it, the column still lists their account.
    expect(await seenBy(dave, '/settings/users')).toEqual(expected);
  });

  it('a viewer: the same as a member', async () => {
    const seen = await seenBy({ id: 'vera', workspaceRole: 'viewer', organizations: [], grants: {} });
    expect(seen).toEqual({
      settings: '/account/profile',
      tabs: [],
      opens: {},
      level: 'Account',
      column: { Account: ['Profile', 'Appearance'] },
    });
  });

  it('a member to whom IAM delegates the organization\'s access: its Roles & permissions alone', async () => {
    const eve: Person = {
      id: 'eve',
      workspaceRole: 'member',
      organizations: [{ ...ACME, role: 'member' }],
      grants: { 'organization:acme': ['iam:ListAttachments'] },
    };
    const seen = await seenBy(eve);
    expect(seen.tabs).toEqual(['Organization', 'Account']);
    expect(seen.level).toBe('Account');
    const organization = await seenBy(eve, seen.opens.Organization);
    expect(organization.column).toEqual({ Organization: ['Roles & permissions'] });
  });

  it('the admin of another organization than the workspace\'s: that one, named in its tab', async () => {
    const nina: Person = {
      id: 'nina',
      workspaceRole: 'member',
      organizations: [
        { ...ACME, role: 'member' },
        { id: 'beta', name: 'Beta', role: 'admin' },
      ],
      grants: { 'organization:beta': [] },
    };
    const seen = await seenBy(nina);
    expect(seen.tabs).toEqual(['Organization · Beta', 'Account']);
    const organization = await seenBy(nina, seen.opens['Organization · Beta']);
    expect(organization.level).toBe('Organization · Beta');
    expect(organization.column['Organization · Beta']).toContain('Members');
  });

  it('someone who may read the system: a Platform tab with System, Activity, Resources and Data', async () => {
    const sam: Person = { id: 'sam', workspaceRole: 'member', organizations: [], grants: { platform: ['nexus:ReadSystem'] } };
    const seen = await seenBy(sam);
    expect(seen.tabs).toEqual(['Platform', 'Account']);
    expect(seen.settings).toBe('/account/profile');
    const platform = await seenBy(sam, seen.opens.Platform);
    expect(platform.level).toBe('Platform');
    expect(Object.keys(platform.column)).toEqual(PLATFORM_GROUPS);
    expect(platform.column.Administration).toEqual(['General', 'Organizations']);
    expect(platform.column.System).toEqual(expect.arrayContaining(['Overview', 'Layers', 'Diagrams']));
    expect(platform.column.Resources).toContain('Models');
  });

  it('someone who may list the users only: a Platform tab with Users alone', async () => {
    const uma: Person = { id: 'uma', workspaceRole: 'member', organizations: [], grants: { platform: ['nexus:ListUsers'] } };
    const seen = await seenBy(uma);
    expect(seen.tabs).toEqual(['Platform', 'Account']);
    expect(seen.opens.Platform).toBe('/settings/users');
    const platform = await seenBy(uma, seen.opens.Platform);
    expect(platform.column).toEqual({ Administration: ['Users'] });
  });
});
