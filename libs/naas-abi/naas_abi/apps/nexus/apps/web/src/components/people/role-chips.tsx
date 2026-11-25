'use client';

/** One of a person's roles in a Users list: a group, or a policy attached to them. */
export type RoleChip = { kind: 'group' | 'policy'; id: string; name: string; scope?: string | null; implied?: boolean };

/** The roles of a Users list's `roles` field, read safely. */
export function readRoleChips(value: unknown): RoleChip[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((r) => {
    if (!r || typeof r !== 'object') return [];
    const { kind, id, name, scope, implied } = r as Record<string, unknown>;
    if ((kind !== 'group' && kind !== 'policy') || typeof id !== 'string') return [];
    return [
      {
        kind,
        id,
        name: typeof name === 'string' && name ? name : id,
        scope: typeof scope === 'string' ? scope : null,
        implied: implied === true,
      },
    ];
  });
}

/**
 * A person's Role as Users lists show it (Workspace, Organization, Platform): their groups, then the
 * policies attached to them (dashed), in the order the API gives; "—" for none.
 */
export function RoleChips({ roles }: { roles: readonly RoleChip[] }) {
  if (roles.length === 0) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="flex flex-wrap gap-1" data-field="role">
      {roles.map((role) => (
        <span
          key={`${role.kind}:${role.id}:${role.scope ?? ''}`}
          data-role={role.kind}
          title={
            role.kind === 'policy'
              ? `Policy attached to them${role.scope ? ` at ${role.scope}` : ''}`
              : role.implied
                ? 'They reach it through their admins group'
                : 'Group'
          }
          className={
            role.kind === 'group'
              ? 'border border-border bg-muted/60 px-1.5 py-0.5 text-[11px]'
              : 'border border-dashed border-primary/60 px-1.5 py-0.5 text-[11px] text-primary'
          }
        >
          {role.name}
        </span>
      ))}
    </span>
  );
}
