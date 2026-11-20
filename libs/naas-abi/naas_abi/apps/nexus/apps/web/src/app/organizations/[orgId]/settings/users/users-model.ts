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

/**
 * Whether "Remove from organization" applies: to anyone but an owner (demoted first, so the last
 * owner never leaves) and oneself. Someone with workspace access only is removed too.
 */
export function removableFromOrganization(
  role: OrganizationMember['role'],
  userId: string,
  selfId: string | null | undefined
): boolean {
  return role !== 'owner' && userId !== selfId;
}

/**
 * How someone leaves: with workspace access only, from every workspace of the organization in one
 * step (`DELETE …/members/{id}/access`); with an org role, the org role is taken
 * (`DELETE …/members/{id}`) and any workspace access stays.
 */
export type OrganizationRemoval = 'all-access' | 'org-role';

export function organizationRemoval(role: OrganizationMember['role']): OrganizationRemoval {
  return role === null ? 'all-access' : 'org-role';
}

/** The confirm dialog of "Remove from organization": what will be taken, and what stays. */
export function removalConfirmation(
  name: string,
  role: OrganizationMember['role'],
  workspaceNames: string[]
): { title: string; description: string; confirmLabel: string } {
  const title = `Remove ${name} from the organization?`;
  if (organizationRemoval(role) === 'all-access') {
    const where =
      workspaceNames.length > 0
        ? `every workspace of this organization (${workspaceNames.join(', ')})`
        : 'every workspace of this organization';
    return {
      title,
      description: `They lose access to ${where}. Their account stays, with what they hold elsewhere.`,
      confirmLabel: 'Remove',
    };
  }
  return {
    title,
    description:
      workspaceNames.length > 0
        ? `Their organization role is removed. Their workspace access stays (${workspaceNames.join(', ')}).`
        : 'Their organization role is removed. Their account stays.',
    confirmLabel: 'Remove',
  };
}
