// Users › Role at a workspace, an organization or the platform: the groups and policies a
// person's Role holds there, the ones it may hold (`GET …/role-options`), and the change asked
// (`PUT …/<id>/roles`). The pure part of the Role editor: the default Role of someone created
// there (Members, and the container's own group), and what adding or removing one gives.

export type RoleOptionKind = 'level' | 'own' | 'admins' | 'group' | 'policy';

/**
 * A group or policy a Role may hold. At an organization, a group of one of its workspaces names
 * it (`workspace`), and says whether it is the workspace's admins group (`administers`).
 */
export type RoleOption = {
  kind: RoleOptionKind;
  id: string;
  name: string;
  level?: 'member' | 'viewer' | null;
  workspace?: string;
  administers?: boolean;
};

export type RoleOptions = { groups: RoleOption[]; policies: RoleOption[] };

/** What the editor holds: group and policy ids. */
export type RoleSelection = { groups: string[]; policies: string[] };

/**
 * Why a change of their Role here leaves one of their groups alone: the container's own group
 * an admin reaches through an admins group, or a group managed in the organization's or the
 * platform's Users.
 */
export type RoleManaged = 'admins' | 'organization' | 'platform';

/** One of the groups a person's Role shows (Users › Role), in its order. */
export type ShownRole = { id: string; name: string; implied: boolean; managed: RoleManaged | null };

/**
 * What a person holds (`GET …/roles`): the ids, each one's name, and the groups their Role
 * shows (`shown`), those a change here leaves alone among them.
 */
export type HeldRoles = RoleSelection & { names: Record<string, string>; shown?: ShownRole[] };

/** A group or policy on a person's page; `managed`: why it cannot be removed here. */
export type HeldItem = RoleOption & { managed?: RoleManaged };

const KIND_ORDER: Record<RoleOptionKind, number> = { own: 0, admins: 1, level: 2, group: 3, policy: 4 };
const MANAGED: readonly string[] = ['admins', 'organization', 'platform'];

/**
 * What a person holds, as their page lists it: their groups as their Role shows them (the
 * container's own first, then what gives them their place, their level, the others), those a
 * change here leaves alone included, then the rest they hold (the level of an admin); and their
 * policies, each named. One the caller is not offered keeps the name IAM gives it, as a plain
 * group or policy.
 */
export function heldItems(options: RoleOptions, held: HeldRoles): { groups: HeldItem[]; policies: HeldItem[] } {
  const known = new Map([...options.groups, ...options.policies].map((o) => [`${o.kind === 'policy' ? 'p' : 'g'}:${o.id}`, o]));
  const named = (id: string, kind: 'group' | 'policy'): RoleOption =>
    known.get(`${kind === 'policy' ? 'p' : 'g'}:${id}`) ?? { kind, id, name: held.names[id] || id, level: null };
  const order = (a: RoleOption, b: RoleOption) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || a.name.localeCompare(b.name);
  const shown = held.shown ?? [];
  const place = new Map(shown.map((s, i) => [s.id, i]));
  const rank = (o: RoleOption) => place.get(o.id) ?? shown.length;
  const mine = new Set(held.groups);
  const fixed: HeldItem[] = shown
    .filter((s) => s.managed && !mine.has(s.id))
    .map((s) => ({ kind: s.implied ? 'own' : 'group', id: s.id, name: s.name, level: null, managed: s.managed ?? undefined }));
  return {
    groups: [...held.groups.map((id) => named(id, 'group')), ...fixed].sort((a, b) => rank(a) - rank(b) || order(a, b)),
    policies: held.policies.map((id) => named(id, 'policy')).sort(order),
  };
}

function readShown(value: unknown): ShownRole[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((row): ShownRole[] => {
    if (!row || typeof row !== 'object') return [];
    const { id, name, implied, managed } = row as Record<string, unknown>;
    if (typeof id !== 'string' || !id) return [];
    return [
      {
        id,
        name: typeof name === 'string' && name ? name : id,
        implied: implied === true,
        managed: typeof managed === 'string' && MANAGED.includes(managed) ? (managed as RoleManaged) : null,
      },
    ];
  });
}

/** `selection` with every one of `picked` added (`withRole`, in order). */
export function withRoles(options: RoleOptions, selection: RoleSelection, picked: RoleOption[]): RoleSelection {
  return picked.reduce((next, option) => withRole(options, next, option), selection);
}

export function readRoleOptions(data: unknown): RoleOptions {
  const read = (items: unknown, fallback: RoleOptionKind): RoleOption[] =>
    (Array.isArray(items) ? items : []).flatMap((item) => {
      if (!item || typeof item !== 'object') return [];
      const { kind, id, name, level, workspace, administers } = item as Record<string, unknown>;
      if (typeof id !== 'string' || !id) return [];
      const known: RoleOptionKind[] = ['level', 'own', 'admins', 'group', 'policy'];
      return [
        {
          kind: known.includes(kind as RoleOptionKind) ? (kind as RoleOptionKind) : fallback,
          id,
          name: typeof name === 'string' && name ? name : id,
          level: level === 'member' || level === 'viewer' ? level : null,
          ...(typeof workspace === 'string' && workspace ? { workspace, administers: administers === true } : {}),
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

/** A member as their page needs them: their Nexus id, name, email, and how they reach the workspace. */
export type MemberRef = { userId: string; name: string; email: string | null; source: 'workspace' | 'organization' };

export type MemberRolesApi = {
  options: (scope: RoleScope) => Promise<RoleOptions>;
  /** A workspace's member whose IAM id is `principalId`, or null. */
  member: (workspaceId: string, principalId: string) => Promise<MemberRef | null>;
  /** What the person holds there, named (what their page lists, a change starts from). */
  held: (scope: RoleScope, userId: string) => Promise<HeldRoles>;
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
        email: typeof row.email === 'string' && row.email ? row.email : null,
        source: row.source === 'organization' ? 'organization' : 'workspace',
      };
    },
    async held(scope, userId) {
      const data = await answer<Partial<HeldRoles>>(
        await fetcher(`${roleBase(scope)}/${encodeURIComponent(userId)}/roles`),
        'Could not load their roles'
      );
      const names: Record<string, string> = {};
      if (data.names && typeof data.names === 'object') {
        for (const [id, name] of Object.entries(data.names)) if (typeof name === 'string' && name) names[id] = name;
      }
      return { groups: ids(data.groups), policies: ids(data.policies), names, shown: readShown(data.shown) };
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
