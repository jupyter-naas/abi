/**
 * Organization settings › Users: the pure part. Rows are the organization's directory: people
 * with an org role, and those linked through a workspace role only (no org role, "—").
 */
import type { OrganizationMember } from '@/stores/organization';

/** What a row with no org role says: linked through a workspace, with no org permission. */
export const WORKSPACE_ACCESS_ONLY = 'Workspace access only';

const ROLE_LABEL: Record<'owner' | 'admin' | 'member', string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
};

const ROLE_RANK: Record<'owner' | 'admin' | 'member', number> = { owner: 0, admin: 1, member: 2 };

/** The role column's text (filters, facets, export): the org role, else "Workspace access only". */
export function orgUserRoleLabel(user: Pick<OrganizationMember, 'role'>): string {
  return user.role ? ROLE_LABEL[user.role] : WORKSPACE_ACCESS_ONLY;
}

/** Owners first, then admins, members, and those with workspace access only. */
export function orgUserRoleRank(user: Pick<OrganizationMember, 'role'>): number {
  return user.role ? ROLE_RANK[user.role] : 3;
}
