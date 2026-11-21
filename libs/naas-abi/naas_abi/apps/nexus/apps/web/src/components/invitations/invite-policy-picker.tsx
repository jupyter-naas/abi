'use client';

import { useEffect, useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { createPeopleApi, type CapabilityGroup } from '@/lib/people';
import { cn } from '@/lib/utils';

/** Where the groups are offered: an organization, or a workspace (its organization's). */
export type CapabilityGroupsAt = { organizationId: string } | { workspaceId: string };

const defaultLoad = (at: CapabilityGroupsAt) => createPeopleApi().capabilityGroups(at);

/**
 * The capability groups a person is put in beside their level (#1589): "Workflow runners",
 * "Models · all", and the groups made for a per-person exception (a seat licence, a pilot),
 * as `GET …/capability-groups` lists them where the person is added. No policy is given to a
 * person any more, so no built-in, service-account or customer policy is offered here. Optional:
 * nothing is shown when there is none to offer or the caller may not list them.
 */
export function CapabilityGroupPicker({
  at,
  value,
  onChange,
  disabled,
  className,
  load = defaultLoad,
}: {
  /** null while it is not known: nothing is asked. */
  at: CapabilityGroupsAt | null;
  value: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
  className?: string;
  /** Tests pass a fake. */
  load?: (at: CapabilityGroupsAt) => Promise<CapabilityGroup[]>;
}) {
  const [groups, setGroups] = useState<CapabilityGroup[]>([]);
  const key = at ? ('organizationId' in at ? `org:${at.organizationId}` : `ws:${at.workspaceId}`) : null;

  useEffect(() => {
    setGroups([]);
    if (!at) return;
    let cancelled = false;
    load(at)
      .then((found) => {
        if (!cancelled) setGroups(found);
      })
      .catch(() => {
        // Not listable here: the person gets their level and workspaces alone.
      });
    return () => {
      cancelled = true;
    };
    // `at` is read through its key: a new object for the same place asks nothing again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, load]);

  if (!groups.length) return null;
  const picked = new Set(value);

  return (
    <fieldset className={cn('space-y-1.5', className)} data-capability-groups>
      <legend className="text-sm font-medium">
        Capability groups <span className="font-normal text-muted-foreground">(optional)</span>
      </legend>
      <p className="text-xs text-muted-foreground">
        Each adds one thing to their level, in their workspaces: running workflows, every model, a seat.
      </p>
      <div className="max-h-36 space-y-1.5 overflow-y-auto border border-border p-2">
        {groups.map((group) => (
          <Checkbox
            key={group.id}
            className="flex"
            label={
              <span className="truncate" title={group.description || group.name}>
                {group.name}
              </span>
            }
            aria-label={`Add to ${group.name}`}
            data-capability={group.id}
            checked={picked.has(group.id)}
            disabled={disabled}
            onCheckedChange={(on) =>
              onChange(on ? [...value.filter((id) => id !== group.id), group.id] : value.filter((id) => id !== group.id))
            }
          />
        ))}
      </div>
    </fieldset>
  );
}
