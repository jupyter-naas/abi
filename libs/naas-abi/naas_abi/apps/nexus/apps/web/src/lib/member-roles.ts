// Users › Role at a workspace: the groups and policies a member's Role holds there, the ones
// it may hold (`GET …/members/role-options`), and the change asked (`PUT …/members/<id>/roles`).
// The pure part of the Role editor: the default Role of someone created in a workspace
// (Members and the workspace's own group), and what adding or removing one gives (one level).

export type RoleOptionKind = 'level' | 'workspace' | 'admins' | 'group' | 'policy';

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
      const known: RoleOptionKind[] = ['level', 'workspace', 'admins', 'group', 'policy'];
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

/** The Role of someone created in a workspace: Members and the workspace's own group. */
export function defaultRole(options: RoleOptions): RoleSelection {
  const own = options.groups.find((g) => g.kind === 'workspace');
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

/** `selection` without `option`; the workspace's own group stays (removing someone takes them out). */
export function withoutRole(selection: RoleSelection, option: RoleOption): RoleSelection {
  if (option.kind === 'workspace') return selection;
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
    return 'They would use nothing in this workspace: keep a level (Members or Viewers), the admins group or a policy';
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
  options: (workspaceId: string) => Promise<RoleOptions>;
  /** The member whose IAM id is `principalId`, or null. */
  member: (workspaceId: string, principalId: string) => Promise<MemberRef | null>;
  /** What the member holds here (what their Role editor starts from). */
  held: (workspaceId: string, userId: string) => Promise<RoleSelection>;
  /** The member as the members list shows them, after the change. */
  set: (workspaceId: string, userId: string, selection: RoleSelection) => Promise<Record<string, unknown>>;
};

export function createMemberRolesApi(fetcher: Fetcher = defaultFetcher): MemberRolesApi {
  const members = (id: string) => `/api/workspaces/${encodeURIComponent(id)}/members`;
  return {
    async options(workspaceId) {
      return readRoleOptions(
        await answer<unknown>(await fetcher(`${members(workspaceId)}/role-options`), 'Could not load the roles')
      );
    },
    async member(workspaceId, principalId) {
      const rows = await answer<Record<string, unknown>[]>(await fetcher(members(workspaceId)), 'Could not load the members');
      const row = (Array.isArray(rows) ? rows : []).find((r) => r.principal_id === principalId);
      if (!row || typeof row.user_id !== 'string') return null;
      return {
        userId: row.user_id,
        name: (typeof row.name === 'string' && row.name) || (typeof row.email === 'string' ? row.email : row.user_id),
        source: row.source === 'organization' ? 'organization' : 'workspace',
      };
    },
    async held(workspaceId, userId) {
      const data = await answer<Partial<RoleSelection>>(
        await fetcher(`${members(workspaceId)}/${encodeURIComponent(userId)}/roles`),
        'Could not load their roles'
      );
      const ids = (value: unknown) => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []);
      return { groups: ids(data.groups), policies: ids(data.policies) };
    },
    async set(workspaceId, userId, selection) {
      return answer<Record<string, unknown>>(
        await fetcher(`${members(workspaceId)}/${encodeURIComponent(userId)}/roles`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(selection),
        }),
        'Could not change their roles'
      );
    },
  };
}
