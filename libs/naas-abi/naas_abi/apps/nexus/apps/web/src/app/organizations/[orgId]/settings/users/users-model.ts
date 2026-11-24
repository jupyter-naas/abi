/**
 * Organization settings › Users: the pure part. Rows are the organization's directory (#1589): its
 * admins, its people, and those who reach it through one of its workspaces only.
 */
import { LEVEL_LABELS } from '@/lib/people';
import type { OrganizationMember } from '@/stores/organization';

/** What a row with no level nor org admin says: linked through a workspace. */
export const WORKSPACE_ACCESS_ONLY = 'Workspace access only';

type Access = Pick<OrganizationMember, 'role' | 'orgAdmin' | 'level'>;

/** The access column's text (filters, facets, export): "Org admin", else the level. */
export function orgUserRoleLabel(user: Access): string {
  if (user.orgAdmin || user.role === 'admin') return 'Org admin';
  const level = user.level ?? (user.role === 'member' || user.role === 'viewer' ? user.role : null);
  return level ? LEVEL_LABELS[level] : WORKSPACE_ACCESS_ONLY;
}

const RANK: Record<string, number> = { 'Org admin': 0, Member: 1, Viewer: 2 };

/** Org admins first, then Members, Viewers, and those with workspace access only. */
export function orgUserRoleRank(user: Access): number {
  return RANK[orgUserRoleLabel(user)] ?? 3;
}

/** Whether "Remove from organization" applies: to anyone but oneself. The last org admin is
 *  kept by the API (409), which the page says. */
export function removableFromOrganization(userId: string, selfId: string | null | undefined): boolean {
  return userId !== selfId;
}

/** The confirm dialog of "Remove from organization": every group of the organization is left
 *  (`DELETE …/members/{id}/access`); the account and their level stay. */
export function removalConfirmation(
  name: string,
  workspaceNames: string[]
): { title: string; description: string; confirmLabel: string } {
  const where =
    workspaceNames.length > 0
      ? `every workspace of this organization (${workspaceNames.join(', ')})`
      : 'every workspace of this organization';
  return {
    title: `Remove ${name} from the organization?`,
    description: `They leave ${where}, its people, its org admins and its capability groups. Their account and level stay, with what they hold elsewhere.`,
    confirmLabel: 'Remove',
  };
}

/** `PUT …/members/{id}/workspaces`: the workspaces picked, each keeping "admin" where they have it. */
export function workspacesBody(
  workspaceIds: string[],
  memberships: { user_id: string; workspace_id: string; role: string }[],
  userId: string
): { workspaces: { id: string; admin: boolean }[] } {
  const admin = new Set(
    memberships.filter((m) => m.user_id === userId && (m.role === 'admin' || m.role === 'owner')).map((m) => m.workspace_id)
  );
  return { workspaces: workspaceIds.map((id) => ({ id, admin: admin.has(id) })) };
}
