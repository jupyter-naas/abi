import type { AttachmentView, GroupView, PrincipalKind } from '@/lib/iam-admin/types';
import type { ScopeMember } from '../access-directory';
import { principalLabel } from '../attachments/attachments-model';
import { isRoleCompanion, principalKindOf, roleOfPolicy, type BuiltInRole } from '../roles/role-change';

export type HeldPolicy = { id: string; name: string };

/** Who holds what at a scope: their built-in role, the policies attached to them there, and
 *  what reaches them through a group holding policies there. */
export type PersonRow = {
  /** As the scope's members name them (the membership routes), else their IAM id. */
  id: string;
  /** Their IAM id: their page lists what IAM holds for it. Empty for a member whose IAM id
   *  is not known (the member routes did not say it, nothing here names it): no page then,
   *  as a Nexus id names nobody in IAM for an account linked from the old login. */
  principalId: string;
  kind: PrincipalKind;
  label: string;
  email: string;
  role: BuiltInRole | null;
  /** The role is the organization's, read-only at a workspace. */
  inherited: boolean;
  /** A member of the scope (the directory knows them): their role changes as a membership. */
  member: boolean;
  /** Attached to them here; a user's role attachment is their `role`, not listed. */
  direct: AttachmentView[];
  /** What IAM attached with the role (the platform companions): shown with it,
   *  never detached by hand. */
  withRole: AttachmentView[];
  viaGroups: { groupId: string; groupLabel: string; policies: HeldPolicy[] }[];
};

const KIND_ORDER: Record<PrincipalKind, number> = { user: 0, group: 1, service_account: 2 };
const ROLE_RANK: Record<BuiltInRole, number> = { owner: 3, admin: 2, member: 1, viewer: 0 };

function higher(a: BuiltInRole | null, b: BuiltInRole | null): BuiltInRole | null {
  if (!a) return b;
  if (!b) return a;
  return ROLE_RANK[a] >= ROLE_RANK[b] ? a : b;
}

/**
 * The rows of People & roles. ``attachments`` are those at the scope, ``members`` the scope's
 * people (none at the platform), ``groups`` the groups holding something there, with their
 * members. A user is a row once, whether a member, a holder or only reached through a group.
 */
export function peopleAt(attachments: AttachmentView[], members: ScopeMember[], groups: GroupView[]): PersonRow[] {
  const rows = new Map<string, PersonRow>();
  const row = (id: string, init: () => Omit<PersonRow, 'principalId' | 'direct' | 'withRole' | 'viaGroups'>): PersonRow => {
    let found = rows.get(id);
    if (!found) {
      found = { ...init(), principalId: id, direct: [], withRole: [], viaGroups: [] };
      rows.set(id, found);
    }
    return found;
  };

  for (const m of members) {
    const member = row(m.userId, () => ({
      id: m.userId,
      kind: 'user',
      label: m.name || m.email || m.userId,
      email: m.email,
      role: m.role,
      inherited: m.inherited,
      member: true,
    }));
    // Their page is their IAM principal's: an account linked from the old login has
    // another id in IAM than in Nexus, which a link must never name.
    member.principalId = m.principalId ?? '';
  }

  // A member's row, found by their IAM id (the member routes say it), else by their
  // email (a member listed without it): one person, one row.
  const byPrincipal = new Map(members.filter((m) => m.principalId).map((m) => [m.principalId!, m.userId]));
  const byEmail = new Map(members.filter((m) => m.email).map((m) => [m.email.toLowerCase(), m.userId]));
  const rowId = (principalId: string, kind: PrincipalKind, email: string | null | undefined) =>
    byPrincipal.get(principalId) ??
    (rows.has(principalId) || kind !== 'user' || !email ? principalId : (byEmail.get(email.toLowerCase()) ?? principalId));

  for (const a of attachments) {
    const kind = a.principal?.kind ?? principalKindOf(a.principal_id);
    const holder = row(rowId(a.principal_id, kind, a.principal?.email), () => ({
      id: a.principal_id,
      kind,
      label: principalLabel(a.principal, a.principal_id),
      email: a.principal?.email ?? '',
      role: null,
      inherited: false,
      member: false,
    }));
    holder.principalId = a.principal_id;
    const role = kind === 'user' ? roleOfPolicy(a.policy_id) : null;
    if (role) {
      // The directory's role is the effective one; an attachment alone (the platform) says it.
      if (!holder.member) holder.role = higher(holder.role, role);
    } else if (isRoleCompanion(a.policy_id)) {
      holder.withRole.push(a);
    } else {
      holder.direct.push(a);
    }
  }

  for (const group of groups) {
    const held = attachments
      .filter((a) => a.principal_id === group.id)
      .map((a) => ({ id: a.policy_id, name: a.policy_name ?? a.policy_id }));
    if (!held.length) continue;
    const groupLabel = group.name ?? group.display_name ?? group.id;
    for (const m of group.members) {
      const person = row(rowId(m.id, m.kind, m.email), () => ({
        id: m.id,
        kind: m.kind,
        label: principalLabel(m, m.id),
        email: m.email ?? '',
        role: null,
        inherited: false,
        member: false,
      }));
      person.principalId = m.id;
      person.viaGroups.push({ groupId: group.id, groupLabel, policies: held });
    }
  }

  return [...rows.values()].sort(
    (a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }),
  );
}

/** The ids of the groups holding something at the scope, to read their members. */
export function groupHolders(attachments: AttachmentView[]): string[] {
  return [...new Set(attachments.filter((a) => a.principal?.kind === 'group').map((a) => a.principal_id))];
}
