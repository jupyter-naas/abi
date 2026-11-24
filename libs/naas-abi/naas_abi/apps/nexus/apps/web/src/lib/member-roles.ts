// Users › Role at a workspace, an organization or the platform: the groups and policies a
// person's Role holds there, the ones it may hold (`GET …/role-options`), and the change asked
// (`PUT …/<id>/roles`). The pure part of the Role editor: the default Role of someone created
// there (Members, and the container's own group), and what adding or removing one gives.

export type RoleOptionKind = 'level' | 'own' | 'admins' | 'group' | 'policy';

export type RoleOption = { kind: RoleOptionKind; id: string; name: string; level?: 'member' | 'viewer' | null };

export type RoleOptions = { groups: RoleOption[]; policies: RoleOption[] };

/** What the editor holds: group and policy ids. */
export type RoleSelection = { groups: string[]; policies: string[] };

export function readRoleOptions(data: unknown): RoleOptions {
  const read = (items: unknown, fallback: RoleOptionKind): RoleOption[] =>
    (Array.isArray(items) ? items : []).flatMap((item) => {
      if (!item || typeof item !== 'object') return [];
      const { kind, id, name, level } = item as Record<string, unknown>;
      if (typeof id !== 'string' || !id) return [];
      const known: RoleOptionKind[] = ['level', 'own', 'admins', 'group', 'policy'];
      return [
        {
          kind: known.includes(kind as RoleOptionKind) ? (kind as RoleOptionKind) : fallback,
          id,
          name: typeof name === 'string' && name ? name : id,
          level: level === 'member' || level === 'viewer' ? level : null,
        },
      ];
    });
  const value = (data ?? {}) as Record<string, unknown>;
  return { groups: read(value.groups, 'group'), policies: read(value.policies, 'policy') };
}

/** The Role of someone created there: Members, and the container's own group (none at the platform). */
export function defaultRole(options: RoleOptions): RoleSelection {
  const own = options.groups.find((g) => g.kind === 'own');
  const members = options.groups.find((g) => g.kind === 'level' && g.level === 'member');
  return { groups: [own?.id, members?.id].filter((id): id is string => !!id), policies: [] };
}

/** The options not in `selection` yet, groups then policies. */
export function addable(options: RoleOptions, selection: RoleSelection): RoleOption[] {
  return [
    ...options.groups.filter((g) => !selection.groups.includes(g.id)),
    ...options.policies.filter((p) => !selection.policies.includes(p.id)),
  ];
}

/** `selection` with `option` added: a level replaces the other one. */
export function withRole(options: RoleOptions, selection: RoleSelection, option: RoleOption): RoleSelection {
  if (option.kind === 'policy') {
    return selection.policies.includes(option.id)
      ? selection
      : { ...selection, policies: [...selection.policies, option.id] };
  }
  const levels = new Set(options.groups.filter((g) => g.kind === 'level').map((g) => g.id));
  const groups = option.kind === 'level' ? selection.groups.filter((id) => !levels.has(id)) : selection.groups;
  return { ...selection, groups: groups.includes(option.id) ? groups : [...groups, option.id] };
}

/** `selection` without `option`; the container's own group stays (removing someone takes them out). */
export function withoutRole(selection: RoleSelection, option: RoleOption): RoleSelection {
  if (option.kind === 'own') return selection;
  return option.kind === 'policy'
    ? { ...selection, policies: selection.policies.filter((id) => id !== option.id) }
    : { ...selection, groups: selection.groups.filter((id) => id !== option.id) };
}

/** Why the Role cannot be someone's, or null: what the API refuses too, said before asking. */
export function roleProblem(options: RoleOptions, selection: RoleSelection, reachesOtherwise = false): string | null {
  const byId = new Map(options.groups.map((g) => [g.id, g]));
  const chosen = selection.groups.map((id) => byId.get(id)).filter((g): g is RoleOption => !!g);
  const levels = chosen.filter((g) => g.kind === 'level');
  if (levels.length > 1) return 'Pick one level: Members or Viewers';
  const admin = chosen.some((g) => g.kind === 'admins');
  if (admin && levels.some((g) => g.level === 'viewer')) {
    return 'A workspace admin is a Member: a Viewer administers nothing';
  }
  if (!levels.length && !admin && !selection.policies.length && !reachesOtherwise) {
    return 'They would use nothing here: keep a level (Members or Viewers), the admins group or a policy';
  }
  return null;
}

type Fetcher = (path: string, init?: RequestInit) => Promise<Response>;

async function defaultFetcher(path: string, init?: RequestInit): Promise<Response> {
  const { authFetch } = await import('@/stores/auth');
  return authFetch(path, init);
}

async function answer<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    let detail = fallback;
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string') detail = data.detail;
    } catch {
      // the fallback says it
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

/** A member as their page needs them: their Nexus id, name, and how they reach the workspace. */
export type MemberRef = { userId: string; name: string; source: 'workspace' | 'organization' };

export type MemberRolesApi = {
  options: (scope: RoleScope) => Promise<RoleOptions>;
  /** A workspace's member whose IAM id is `principalId`, or null. */
  member: (workspaceId: string, principalId: string) => Promise<MemberRef | null>;
  /** What the person holds there (what their Role editor starts from). */
  held: (scope: RoleScope, userId: string) => Promise<RoleSelection>;
  /** Make their Role there `selection`. */
  set: (scope: RoleScope, userId: string, selection: RoleSelection) => Promise<Record<string, unknown>>;
};

/** Where a Role is: a workspace, an organization, or the platform. */
export type RoleScope = { kind: 'workspace'; id: string } | { kind: 'organization'; id: string } | { kind: 'platform' };

/** The people of a scope, under which its Role routes are. */
export function roleBase(scope: RoleScope): string {
  if (scope.kind === 'workspace') return `/api/workspaces/${encodeURIComponent(scope.id)}/members`;
  if (scope.kind === 'organization') return `/api/organizations/${encodeURIComponent(scope.id)}/members`;
  return '/api/admin/users';
}

export function createMemberRolesApi(fetcher: Fetcher = defaultFetcher): MemberRolesApi {
  const ids = (value: unknown) => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []);
  return {
    async options(scope) {
      return readRoleOptions(await answer<unknown>(await fetcher(`${roleBase(scope)}/role-options`), 'Could not load the roles'));
    },
    async member(workspaceId, principalId) {
      const rows = await answer<Record<string, unknown>[]>(
        await fetcher(roleBase({ kind: 'workspace', id: workspaceId })),
        'Could not load the members'
      );
      const row = (Array.isArray(rows) ? rows : []).find((r) => r.principal_id === principalId);
      if (!row || typeof row.user_id !== 'string') return null;
      return {
        userId: row.user_id,
        name: (typeof row.name === 'string' && row.name) || (typeof row.email === 'string' ? row.email : row.user_id),
        source: row.source === 'organization' ? 'organization' : 'workspace',
      };
    },
    async held(scope, userId) {
      const data = await answer<Partial<RoleSelection>>(
        await fetcher(`${roleBase(scope)}/${encodeURIComponent(userId)}/roles`),
        'Could not load their roles'
      );
      return { groups: ids(data.groups), policies: ids(data.policies) };
    },
    async set(scope, userId, selection) {
      return answer<Record<string, unknown>>(
        await fetcher(`${roleBase(scope)}/${encodeURIComponent(userId)}/roles`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(selection),
        }),
        'Could not change their roles'
      );
    },
  };
}
