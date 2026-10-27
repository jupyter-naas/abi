/**
 * A person's built-in role in an organization or a workspace: the one code every page uses to
 * change it (Roles & permissions › People & roles, workspace Members, an org user's profile).
 *
 * A role is IAM's `builtin.<role>` attachment at the scope, but it changes through the
 * membership routes, never a bare attach: they keep what goes with a role (the org-wide
 * mirror of an org owner or admin, the platform companions, owner protection), and IAM decides
 * the change as the caller.
 */
import { authFetch } from '@/stores/auth';
import type { AccessLevel } from '../access-scope';

export type BuiltInRole = 'owner' | 'admin' | 'member' | 'viewer';

export const BUILT_IN_ROLES: BuiltInRole[] = ['viewer', 'member', 'admin', 'owner'];

export const ROLE_LABELS: Record<BuiltInRole, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
};

/** `builtin.<role>`, the policy IAM attaches for a role. */
export function rolePolicyId(role: BuiltInRole): string {
  return `builtin.${role}`;
}

/** The role a built-in role policy stands for, else null. */
export function roleOfPolicy(policyId: string): BuiltInRole | null {
  const role = policyId.startsWith('builtin.') ? policyId.slice('builtin.'.length) : '';
  return (BUILT_IN_ROLES as string[]).includes(role) ? (role as BuiltInRole) : null;
}

/** The roles a page may give: never owner (owners come from the configuration or a transfer);
 *  an organization has no viewers. */
export function assignableRoles(level: AccessLevel): BuiltInRole[] {
  if (level === 'workspace') return ['member', 'viewer', 'admin'];
  if (level === 'organization') return ['member', 'admin'];
  return [];
}

/** Whether a role may be changed here: not an owner's, not one inherited from the
 *  organization, not the caller's own. */
export function roleChangeable(target: {
  role: BuiltInRole | null;
  inherited: boolean;
  userId: string;
  selfId: string | null | undefined;
}): boolean {
  return target.role !== 'owner' && !target.inherited && target.userId !== target.selfId;
}

export type RoleTarget = { level: 'organization'; organizationId: string } | { level: 'workspace'; workspaceId: string };

/** The membership route of a person at a level. */
export function memberPath(target: RoleTarget, userId: string): string {
  const id = encodeURIComponent(userId);
  return target.level === 'workspace'
    ? `/api/workspaces/${encodeURIComponent(target.workspaceId)}/members/${id}`
    : `/api/organizations/${encodeURIComponent(target.organizationId)}/members/${id}`;
}

async function detailOf(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg || String(d)).join(', ');
  } catch {
    // no JSON body
  }
  return fallback;
}

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

/** Give `userId` `role` at the target; throws IAM's or the route's words when refused. */
export async function changeMemberRole(
  target: RoleTarget,
  userId: string,
  role: BuiltInRole,
  fetcher: Fetcher = authFetch,
): Promise<void> {
  const response = await fetcher(memberPath(target, userId), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  });
  if (!response.ok) throw new Error(await detailOf(response, 'Could not change the role.'));
}
