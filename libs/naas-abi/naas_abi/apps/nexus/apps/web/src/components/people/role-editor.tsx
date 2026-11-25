'use client';

import { X } from 'lucide-react';
import { Select } from '@/components/ui/input';
import {
  addable,
  roleProblem,
  withRole,
  withoutRole,
  type RoleOption,
  type RoleOptions,
  type RoleSelection,
} from '@/lib/member-roles';

const KIND_ORDER: Record<RoleOption['kind'], number> = { own: 0, admins: 1, level: 2, group: 3, policy: 4 };

/**
 * The Role of a person at a workspace (Users › Create user, a person's page): the groups and
 * policies it holds, as removable tags (the workspace's own group stays: removing someone takes
 * them out), and the ones to add. A level (Members, Viewers) replaces the other one; what the
 * API would refuse is said under it (`roleProblem`). Ids the caller is not offered stay in
 * `value` untouched.
 */
export function RoleEditor({
  options,
  value,
  onChange,
  disabled = false,
  reachesOtherwise = false,
}: {
  options: RoleOptions;
  value: RoleSelection;
  onChange: (next: RoleSelection) => void;
  disabled?: boolean;
  /** Another role gives them the workspace (an organization's admin): no level needed. */
  reachesOtherwise?: boolean;
}) {
  const known = new Map([...options.groups, ...options.policies].map((o) => [`${o.kind === 'policy' ? 'p' : 'g'}:${o.id}`, o]));
  const chosen = [
    ...value.groups.map((id) => known.get(`g:${id}`)),
    ...value.policies.map((id) => known.get(`p:${id}`)),
  ]
    .filter((o): o is RoleOption => !!o)
    .sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || a.name.localeCompare(b.name));
  const more = addable(options, value);
  const problem = roleProblem(options, value, reachesOtherwise);
  return (
    <div className="space-y-2" data-role-editor>
      <div className="flex flex-wrap gap-1.5" data-role-tags>
        {chosen.length === 0 && <span className="text-xs text-muted-foreground">No role</span>}
        {chosen.map((option) => (
          <span
            key={`${option.kind}:${option.id}`}
            data-role={option.kind}
            className={
              option.kind === 'policy'
                ? 'inline-flex items-center gap-1 border border-dashed border-primary/60 px-1.5 py-0.5 text-xs text-primary'
                : 'inline-flex items-center gap-1 border border-border bg-muted/60 px-1.5 py-0.5 text-xs'
            }
          >
            {option.name}
            {option.kind !== 'own' && !disabled && (
              <button
                type="button"
                aria-label={`Remove ${option.name}`}
                className="text-muted-foreground hover:text-foreground"
                onClick={() => onChange(withoutRole(value, option))}
                data-action="remove-role"
              >
                <X size={12} />
              </button>
            )}
          </span>
        ))}
      </div>
      {!disabled && more.length > 0 && (
        <Select
          value=""
          aria-label="Add a group or policy"
          className="h-8 max-w-sm"
          data-field="add-role"
          onChange={(event) => {
            const option = more.find((o) => `${o.kind}:${o.id}` === event.target.value);
            if (option) onChange(withRole(options, value, option));
          }}
        >
          <option value="">Add a group or policy…</option>
          {more.some((o) => o.kind !== 'policy') && (
            <optgroup label="Groups">
              {more
                .filter((o) => o.kind !== 'policy')
                .map((o) => (
                  <option key={o.id} value={`${o.kind}:${o.id}`}>
                    {o.kind === 'level' ? `${o.name} (level, in all their workspaces)` : o.name}
                  </option>
                ))}
            </optgroup>
          )}
          {more.some((o) => o.kind === 'policy') && (
            <optgroup label="Policies">
              {more
                .filter((o) => o.kind === 'policy')
                .map((o) => (
                  <option key={o.id} value={`${o.kind}:${o.id}`}>
                    {o.name}
                  </option>
                ))}
            </optgroup>
          )}
        </Select>
      )}
      {problem && (
        <p className="text-xs text-destructive" role="alert" data-role-problem>
          {problem}
        </p>
      )}
    </div>
  );
}
