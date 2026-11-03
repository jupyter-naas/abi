/**
 * Who owns a policy listed on a Roles & permissions page, as the page shows it: the owner's
 * name (its containers named as the caller may list them, `GET /resources`), what the caller
 * may do with the owner's policies (`GET /access?scope=<owner>`), and the owner's own Roles &
 * permissions page, opened on the policy. A policy is edited at its owner, wherever it is listed.
 */
import { useEffect, useMemo, useState } from 'react';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import { PLATFORM, parseScope, type ContainerStep } from '../access-scope';

export type PolicyOwner = {
  /** The owner's container, `abi:` for the platform. */
  scope: string;
  /** "Workspace Alpha (Acme)", "Organization Acme", "Platform": the ids while names are not
   *  known, or when the caller may not list them. */
  label: string;
  /** Whether the owner's Roles & permissions page is linked (``ownerHref``): another level's,
   *  where the caller may manage something. */
  opens: boolean;
  /** At the owner: IAM's answer, false until known. */
  canUpdate: boolean;
  canDelete: boolean;
};

/** A container named by the steps up to and including ``index``. */
function containerAt(steps: ContainerStep[], index: number, scope: string): string {
  // The scope's own tokens, so each container is written exactly as IAM wrote the owner.
  const tokens = scope.slice(PLATFORM.length).split('/');
  return PLATFORM + tokens.slice(0, (index + 1) * 2).join('/');
}

const KIND: Record<string, string> = { 'nexus:organization': 'Organization', 'nexus:workspace': 'Workspace' };

function stepWords(step: ContainerStep, name: string | undefined): string {
  const kind = KIND[`${step.service}:${step.type}`] ?? step.type.replace(/_/g, ' ');
  return `${kind[0].toUpperCase()}${kind.slice(1)} ${name || step.id}`;
}

/** The owner in words: its container, then what it sits in, in parentheses
 *  (`Workspace Alpha (Acme)`), each named from ``names`` (container → name) or by its id. */
export function ownerLabel(scope: string | null | undefined, names: Record<string, string> = {}): string {
  const owner = scope ?? PLATFORM;
  const parsed = parseScope(owner);
  if (!parsed || parsed.below) return owner;
  const steps = parsed.containers;
  if (steps.length === 0) return 'Platform';
  const named = steps.map((step, i) => names[containerAt(steps, i, owner)]);
  const last = steps.length - 1;
  const own = stepWords(steps[last], named[last]);
  if (last === 0) return own;
  const above = steps
    .slice(0, last)
    .map((step, i) => named[i] || step.id)
    .reverse()
    .join(', ');
  return `${own} (${above})`;
}

/** "Owned by workspace Alpha (Acme)", "Owned by the platform": ``label`` in a sentence. */
export function ownedBy(label: string): string {
  return label === 'Platform' ? 'Owned by the platform' : `Owned by ${label[0].toLowerCase()}${label.slice(1)}`;
}

/** The owner's Roles & permissions page, on its Policies opened at ``policyId``: the platform's,
 *  an organization's or a workspace's; none for a container another module declares. */
export function ownerHref(scope: string | null | undefined, policyId?: string): string | null {
  const owner = scope ?? PLATFORM;
  const parsed = parseScope(owner);
  if (!parsed || parsed.below) return null;
  const last = parsed.containers[parsed.containers.length - 1];
  let path: string | null = null;
  if (!last) path = '/settings/roles';
  else if (last.service === 'nexus' && last.type === 'organization') {
    path = `/organizations/${encodeURIComponent(last.id)}/settings/roles`;
  } else if (last.service === 'nexus' && last.type === 'workspace') {
    path = `/workspace/${encodeURIComponent(last.id)}/settings/permissions`;
  }
  if (!path) return null;
  const query = new URLSearchParams({ section: 'policies' });
  if (policyId) query.set('policy', policyId);
  return `${path}?${query.toString()}`;
}

/** The containers to name for ``owners``: each step of each, once. */
function containersOf(owners: string[]): { container: string; step: ContainerStep }[] {
  const found = new Map<string, ContainerStep>();
  for (const owner of owners) {
    const parsed = parseScope(owner);
    if (!parsed || parsed.below) continue;
    parsed.containers.forEach((step, i) => found.set(containerAt(parsed.containers, i, owner), step));
  }
  return [...found].map(([container, step]) => ({ container, step }));
}

/** A container's name, as the caller lists it at the container itself; none when they may not. */
async function nameOf(api: IamAdminApi, container: string, step: ContainerStep): Promise<string | null> {
  try {
    const page = await api.resources({ scope: container, service: step.service, type: step.type, q: step.id, limit: 5 });
    return page.items.find((item) => item.name === container)?.label || null;
  } catch {
    return null;
  }
}

type Rights = { update: boolean; delete: boolean; any: boolean };

async function rightsAt(api: IamAdminApi, owner: string): Promise<Rights> {
  try {
    const view = await api.access(owner === PLATFORM ? undefined : owner);
    const actions = view?.actions ?? {};
    return {
      update: !!actions['iam:UpdatePolicy'],
      delete: !!actions['iam:DeletePolicy'],
      any: Object.values(actions).some(Boolean),
    };
  } catch {
    return { update: false, delete: false, any: false };
  }
}

/**
 * The owners of the policies a page lists, by owner scope. ``here`` is the page's own scope:
 * its rights are the page's (``can``), so IAM is asked only about the others, once each.
 */
export function usePolicyOwners(
  api: IamAdminApi,
  scopes: (string | null | undefined)[],
  here: string,
  can: (action: string) => boolean,
): Record<string, PolicyOwner> {
  const owners = useMemo(() => [...new Set(scopes.map((s) => s ?? PLATFORM))].sort(), [scopes]);
  const key = owners.join('\n');
  const [names, setNames] = useState<Record<string, string>>({});
  const [rights, setRights] = useState<Record<string, Rights>>({});

  useEffect(() => {
    let cancelled = false;
    for (const { container, step } of containersOf(owners)) {
      if (container in names) continue;
      void nameOf(api, container, step).then((name) => {
        if (!cancelled && name) setNames((current) => ({ ...current, [container]: name }));
      });
    }
    for (const owner of owners) {
      if (owner === here || owner in rights) continue;
      void rightsAt(api, owner).then((found) => {
        if (!cancelled) setRights((current) => ({ ...current, [owner]: found }));
      });
    }
    return () => {
      cancelled = true;
    };
    // Asked again only for an owner, or a container, not asked yet.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, key, here]);

  return useMemo(() => {
    const found: Record<string, PolicyOwner> = {};
    for (const owner of owners) {
      const atOwner =
        owner === here
          ? { update: can('iam:UpdatePolicy'), delete: can('iam:DeletePolicy'), any: true }
          : rights[owner] ?? { update: false, delete: false, any: false };
      found[owner] = {
        scope: owner,
        label: ownerLabel(owner, names),
        opens: owner !== here && atOwner.any && ownerHref(owner) !== null,
        canUpdate: atOwner.update,
        canDelete: atOwner.delete,
      };
    }
    return found;
  }, [owners, here, can, rights, names]);
}
