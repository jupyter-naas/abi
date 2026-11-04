/**
 * What a person or a group holds at every level, as one list: each role, policy and group
 * grant IAM lets the viewer list (`GET /attachments?principal_id=` across levels, and the
 * same for each of their groups, `GET /principals/{id}/groups`). The person's page, the
 * group's page and a policy's attachments share these rows' words.
 */
import type { AttachmentView, PrincipalView } from '@/lib/iam-admin/types';
import { PLATFORM, parseScope } from '../access-scope';
import { principalLabel } from '../attachments/attachments-model';
import { ownerLabel } from '../policies/policy-owners';
import { isRoleCompanion, roleOfPolicy, type BuiltInRole, type RoleTarget } from '../roles/role-change';

export type HoldingRow = {
  attachment: AttachmentView;
  /** The group it comes through; null: attached to the principal itself. */
  via: { id: string; label: string } | null;
  /** A user's built-in role (`builtin.<role>`): a membership, changed as on Members. */
  role: BuiltInRole | null;
  /** What IAM attaches with a role and removes with it: never detached by hand. */
  companion: boolean;
};

/** A group, and what IAM lets the viewer list of its attachments. */
export type GroupHoldings = { group: PrincipalView; attachments: AttachmentView[] };

/**
 * Where an attachment is, in words: as the Owner column names a container (``ownerLabel``,
 * from ``names``, as the viewer may list them), a scope below one as that container "and all
 * below it", an unscoped attachment as everywhere.
 */
export function levelLabel(scope: string | null | undefined, names: Record<string, string> = {}): string {
  if (scope === null || scope === undefined) return 'Everywhere';
  const parsed = parseScope(scope);
  if (!parsed) return scope;
  if (!parsed.below) return ownerLabel(scope, names);
  const container = scope.slice(0, -'/*'.length);
  return `${ownerLabel(container || PLATFORM, names)}, and all below it`;
}

/** The membership a role at ``scope`` is: an organization's or a workspace's; none for a role
 *  elsewhere (below a container: the organization's mirror of its role, read-only). */
export function roleTargetOf(scope: string | null | undefined): RoleTarget | null {
  const parsed = parseScope(scope);
  if (!parsed || parsed.below) return null;
  const last = parsed.containers[parsed.containers.length - 1];
  if (!last || last.service !== 'nexus') return null;
  if (last.type === 'organization') return { level: 'organization', organizationId: last.id };
  if (last.type === 'workspace') return { level: 'workspace', workspaceId: last.id };
  return null;
}

/** How deep a level is: everywhere and the platform first, then each container below. */
function depth(scope: string | null): number {
  if (scope === null) return -1;
  const parsed = parseScope(scope);
  if (!parsed) return 99;
  return parsed.containers.length * 2 + (parsed.below ? 1 : 0);
}

function row(attachment: AttachmentView, via: HoldingRow['via']): HoldingRow {
  const user = (attachment.principal?.kind ?? 'user') === 'user';
  return {
    attachment,
    via,
    role: user && !via ? roleOfPolicy(attachment.policy_id) : null,
    companion: !via && isRoleCompanion(attachment.policy_id),
  };
}

/** Attachments from the top level down: everywhere and the platform first, then each
 *  container, a level's own before what is below it. */
export function byLevel(a: AttachmentView, b: AttachmentView): number {
  return depth(a.scope) - depth(b.scope) || (a.scope ?? '').localeCompare(b.scope ?? '');
}

const byName = (a: string, b: string) => a.localeCompare(b, undefined, { sensitivity: 'base' });

/**
 * The rows of a principal's access: ``direct`` (attached to them) and what each of their
 * ``groups`` holds, from the top level down; at a level, roles, then their own policies, then
 * what comes through a group, each by name.
 */
export function holdingRows(direct: AttachmentView[], groups: GroupHoldings[]): HoldingRow[] {
  const rows = [
    ...direct.map((a) => row(a, null)),
    ...groups.flatMap(({ group, attachments }) => {
      const via = { id: group.id, label: principalLabel(group, group.id) };
      return attachments.map((a) => row(a, via));
    }),
  ];
  const rank = (r: HoldingRow) => (r.companion ? 0 : r.role ? 1 : r.via ? 3 : 2);
  return rows.sort(
    (a, b) =>
      byLevel(a.attachment, b.attachment) ||
      rank(a) - rank(b) ||
      byName(a.attachment.policy_name ?? a.attachment.policy_id, b.attachment.policy_name ?? b.attachment.policy_id),
  );
}

/** The scopes the rows name: where each is attached and where each policy is owned. */
export function scopesOf(rows: HoldingRow[]): (string | null)[] {
  return rows.flatMap((r) => [r.attachment.scope, r.attachment.policy_owner_scope ?? null]);
}
