/**
 * Where each Access page lives at each level, a person's page included, and where the old
 * Roles & permissions addresses go. No React here: src/middleware.ts calls it.
 *
 * - Platform: Settings › Platform › Access, `/settings/access/<page>[/<id>]`; a person's page
 *   is under Users, `/settings/users/<IAM id>`.
 * - Organization: `/organizations/<org>/settings/{policies,groups}[/<id>]`; a person's page
 *   is under Members, `/organizations/<org>/settings/users/<id>`.
 * - Workspace: `/workspace/<ws>/settings/{policies,groups}[/<id>]`; a person's page is under
 *   Members, `/workspace/<ws>/settings/members/<IAM id>`.
 */
import { PLATFORM_USERS_PATH } from '@/app/settings/users/users-model';
import { parseScope, PLATFORM } from './access-scope';

/** The Access pages; an organization and a workspace have Policies and Groups. */
export type AccessPage = 'policies' | 'groups' | 'service-accounts' | 'approvals' | 'simulator' | 'audit';

/** The pages an organization and a workspace have. */
export type ContainerAccessPage = Extract<AccessPage, 'policies' | 'groups'>;

/** Settings › Platform › Access: the index sends the caller to the first page they hold. */
export const PLATFORM_ACCESS_PATH = '/settings/access';

/** The page that creates a policy, in place of a policy's id. */
export const NEW_POLICY = 'new';

const tail = (id?: string | null) => (id ? `/${encodeURIComponent(id)}` : '');

export function platformAccessPath(page: AccessPage, id?: string | null): string {
  return `${PLATFORM_ACCESS_PATH}/${page}${tail(id)}`;
}

export function organizationAccessPath(orgId: string, page: ContainerAccessPage, id?: string | null): string {
  return `/organizations/${encodeURIComponent(orgId)}/settings/${page}${tail(id)}`;
}

export function workspaceAccessPath(workspaceId: string, page: ContainerAccessPage, id?: string | null): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/settings/${page}${tail(id)}`;
}

export function platformPersonPath(personId: string): string {
  return `${PLATFORM_USERS_PATH}${tail(personId)}`;
}

export function organizationPersonPath(orgId: string, personId: string): string {
  return `/organizations/${encodeURIComponent(orgId)}/settings/users${tail(personId)}`;
}

export function workspacePersonPath(workspaceId: string, personId: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/settings/members${tail(personId)}`;
}

function decoded(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** What a page's address has open below its own (``base``): a policy's or a group's id, a
 *  person's, decoded; null on the page itself. */
export function pageFocus(pathname: string | null | undefined, base: string): string | null {
  const path = (pathname ?? '').replace(/[?#].*$/, '');
  if (!path.startsWith(`${base}/`)) return null;
  const [segment] = path.slice(base.length + 1).split('/');
  return segment ? decoded(segment) : null;
}

/** A page of the level a container names (`abi:` the platform, an organization's, a
 *  workspace's), or null for a container another module declares or a scope below one. */
export function accessPathAt(scope: string | null | undefined, page: ContainerAccessPage, id?: string | null): string | null {
  const parsed = parseScope(scope ?? PLATFORM);
  if (!parsed || parsed.below) return null;
  const last = parsed.containers[parsed.containers.length - 1];
  if (!last) return platformAccessPath(page, id);
  if (last.service !== 'nexus') return null;
  if (last.type === 'organization') return organizationAccessPath(last.id, page, id);
  if (last.type === 'workspace') return workspaceAccessPath(last.id, page, id);
  return null;
}

/** What an old Roles & permissions address opened: a person (or the people), a page and
 *  what it had open, or nothing named (the level's first page). */
type OldTarget = { people: true; person: string | null } | { people: false; page: AccessPage | null; id: string | null };

const PLATFORM_ONLY: readonly AccessPage[] = ['service-accounts', 'approvals', 'simulator', 'audit'];
const OLD_QUERY = ['section', 'person', 'group', 'policy'];

function oldTarget(params: URLSearchParams): OldTarget {
  const section = params.get('section');
  const person = params.get('person');
  const group = params.get('group');
  const policy = params.get('policy');
  if (section === 'people' || (!section && person)) return { people: true, person };
  if (section === 'groups' || (!section && group)) return { people: false, page: 'groups', id: group };
  if (section === 'policies' || (!section && policy)) return { people: false, page: 'policies', id: policy };
  const page = PLATFORM_ONLY.find((p) => p === section) ?? null;
  return { people: false, page, id: null };
}

/** The query an old address kept: what it named of its sections goes into the path. */
function keptQuery(params: URLSearchParams): string {
  const rest = new URLSearchParams(params);
  for (const key of OLD_QUERY) rest.delete(key);
  const query = rest.toString();
  return query ? `?${query}` : '';
}

const OLD_PLATFORM = /^\/settings\/roles(?:\/.*)?$/;
const OLD_ORGANIZATION = /^\/organizations\/([^/]+)\/settings\/roles(?:\/.*)?$/;
const OLD_WORKSPACE = /^((?:\/org\/[^/]+)?\/workspace\/([^/]+))\/settings\/permissions(?:\/.*)?$/;

/** The platform's old Roles & permissions (`/settings/roles?section=…`), as a path now. */
export function platformRolesRedirect(params: URLSearchParams): string {
  const target = oldTarget(params);
  const path = target.people
    ? target.person
      ? platformPersonPath(target.person)
      : PLATFORM_USERS_PATH
    : target.page
      ? platformAccessPath(target.page, target.id)
      : PLATFORM_ACCESS_PATH;
  return `${path}${keptQuery(params)}`;
}

/**
 * Where an old Roles & permissions address goes, with what it opened, or null when the path is
 * not one: People & roles to Users (the platform) or Members (an organization, a workspace),
 * a person to their page there; Groups, Policies and the platform's other sections to their
 * page, with the group or the policy it had open; nothing named to the level's first page
 * (the platform's Access index, an organization's or a workspace's Policies).
 * - `/settings/roles?section=…` (Platform);
 * - `/organizations/<org>/settings/roles?section=…`;
 * - `/workspace/<ws>/settings/permissions?section=…`, also behind an org's `/org/<slug>` prefix.
 */
export function oldAccessRedirect(pathname: string, search = ''): string | null {
  const params = new URLSearchParams(search);
  if (OLD_PLATFORM.test(pathname)) return platformRolesRedirect(params);

  const target = oldTarget(params);
  const query = keptQuery(params);
  const organization = OLD_ORGANIZATION.exec(pathname);
  if (organization) {
    const orgId = decodeURIComponent(organization[1]);
    if (target.people) {
      return `${target.person ? organizationPersonPath(orgId, target.person) : `/organizations/${organization[1]}/settings/users`}${query}`;
    }
    const page = target.page === 'groups' ? 'groups' : 'policies';
    return `${organizationAccessPath(orgId, page, target.page === page ? target.id : null)}${query}`;
  }

  const workspace = OLD_WORKSPACE.exec(pathname);
  if (workspace) {
    const [, base] = workspace;
    if (target.people) {
      return `${base}/settings/members${target.person ? tail(target.person) : ''}${query}`;
    }
    const page = target.page === 'groups' ? 'groups' : 'policies';
    return `${base}/settings/${page}${target.page === page ? tail(target.id) : ''}${query}`;
  }
  return null;
}
