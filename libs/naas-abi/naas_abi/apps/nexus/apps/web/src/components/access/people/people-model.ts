import type { AttachmentView, GroupView, PrincipalKind } from '@/lib/iam-admin/types';
import type { ScopeMember } from '../access-directory';
import { principalLabel } from '../attachments/attachments-model';
import { roleOfPolicy, type BuiltInRole } from '../roles/role-change';

export type HeldPolicy = { id: string; name: string };

/** Who holds what at a scope: their built-in role, the policies attached to them there, and
 *  what reaches them through a group holding policies there. */
export type PersonRow = {
  id: string;
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
  const row = (id: string, init: () => Omit<PersonRow, 'direct' | 'viaGroups'>): PersonRow => {
    let found = rows.get(id);
    if (!found) {
      found = { ...init(), direct: [], viaGroups: [] };
      rows.set(id, found);
    }
    return found;
  };

  for (const m of members) {
    row(m.userId, () => ({
      id: m.userId,
      kind: 'user',
      label: m.name || m.email || m.userId,
      email: m.email,
      role: m.role,
      inherited: m.inherited,
      member: true,
    }));
  }

  // A member's account id is their IAM id, except an account linked from the old login,
  // whose IAM user is found by its email: one person, one row.
  const byEmail = new Map(members.filter((m) => m.email).map((m) => [m.email.toLowerCase(), m.userId]));
  const rowId = (principalId: string, kind: PrincipalKind, email: string | null | undefined) =>
    rows.has(principalId) || kind !== 'user' || !email ? principalId : (byEmail.get(email.toLowerCase()) ?? principalId);

  for (const a of attachments) {
    const kind = a.principal?.kind ?? 'user';
    const holder = row(rowId(a.principal_id, kind, a.principal?.email), () => ({
      id: a.principal_id,
      kind,
      label: principalLabel(a.principal, a.principal_id),
      email: a.principal?.email ?? '',
      role: null,
      inherited: false,
      member: false,
    }));
    const role = kind === 'user' ? roleOfPolicy(a.policy_id) : null;
    if (role) {
      // The directory's role is the effective one; an attachment alone (the platform) says it.
      if (!holder.member) holder.role = higher(holder.role, role);
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
