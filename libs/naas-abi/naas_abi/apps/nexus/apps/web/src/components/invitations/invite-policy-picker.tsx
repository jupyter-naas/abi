'use client';

import { useEffect, useMemo, useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { createIamAdminApi, type IamAdminApi } from '@/lib/iam-admin/api';
import type { AttachablePolicy } from '@/lib/iam-admin/types';
import { invitablePolicies } from '@/lib/invitations';
import { cn } from '@/lib/utils';

/**
 * The policies an invitation attaches beside the role, at the invite's scope
 * (`abi:<org>:<ws>`, `abi:<org>:-` for the organization): the customer policies IAM lets the
 * inviter attach there (`attachable`, as Roles & permissions' attach form, those of the levels
 * above included). Features come from such policies (`nexus:UseFeature`), not from the role.
 * Optional: nothing is shown when there is none to offer or the inviter may not list them.
 */
export function InvitePolicyPicker({
  scope,
  value,
  onChange,
  disabled,
  className,
  api,
}: {
  /** null while the scope is not known: nothing is asked. */
  scope: string | null;
  value: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
  className?: string;
  /** Tests pass a fake. */
  api?: Pick<IamAdminApi, 'attachable'>;
}) {
  const client = useMemo(() => api ?? createIamAdminApi(), [api]);
  const [policies, setPolicies] = useState<AttachablePolicy[]>([]);

  useEffect(() => {
    setPolicies([]);
    if (!scope) return;
    let cancelled = false;
    client
      .attachable(scope)
      .then((found) => {
        if (!cancelled) setPolicies(invitablePolicies(found.items));
      })
      .catch(() => {
        // No access to the policies here: the invitation carries the role alone.
      });
    return () => {
      cancelled = true;
    };
  }, [client, scope]);

  if (!policies.length) return null;
  const picked = new Set(value);

  return (
    <fieldset className={cn('space-y-1.5', className)} data-invite-policies>
      <legend className="text-sm font-medium">
        Policies <span className="font-normal text-muted-foreground">(optional)</span>
      </legend>
      <p className="text-xs text-muted-foreground">
        Attached here with the role (features come from policies): right away for someone with an
        account, at their first sign-in otherwise.
      </p>
      {atOrganization(scope) ? (
        <p className="text-xs text-muted-foreground" data-invite-policies-org>
          These attach to the organization itself: they reach none of its workspaces&apos;
          features. Invite to a workspace to give someone its &quot;Features of …&quot;.
        </p>
      ) : null}
      <div className="max-h-36 space-y-1.5 overflow-y-auto border border-border p-2">
        {policies.map((policy) => (
          <Checkbox
            key={policy.id}
            className="flex"
            label={
              <span className="truncate" title={policy.description || policy.id}>
                {policy.name}
              </span>
            }
            aria-label={`Attach ${policy.name}`}
            data-policy={policy.id}
            checked={picked.has(policy.id)}
            disabled={disabled}
            onCheckedChange={(on) =>
              onChange(on ? [...value.filter((id) => id !== policy.id), policy.id] : value.filter((id) => id !== policy.id))
            }
          />
        ))}
      </div>
    </fieldset>
  );
}

/** An organization's own scope (`abi:<org>:-`): what attaches there reaches no workspace. */
export function atOrganization(scope: string | null): boolean {
  return Boolean(scope && scope.endsWith(':-'));
}
