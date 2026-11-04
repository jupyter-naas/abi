/**
 * Who owns a policy listed on a Roles & permissions page, as the page shows it: the owner's
 * name (its containers named as the caller may list them, `GET /resources`), what the caller
 * may do with the owner's policies (`GET /access?scope=<owner>`), and the owner's own Roles &
 * permissions page, opened on the policy. A policy is edited at its owner, wherever it is listed.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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

/** The containers to name for ``scopes``: each step of each, once (a scope below a container,
 *  `<container>/*`, names that container's steps). */
function containersOf(scopes: string[]): { container: string; step: ContainerStep }[] {
  const found = new Map<string, ContainerStep>();
  for (const scope of scopes) {
    const parsed = parseScope(scope);
    if (!parsed) continue;
    parsed.containers.forEach((step, i) => found.set(containerAt(parsed.containers, i, scope), step));
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

/** The key of a scope for ``useActionsAt``: the platform (`abi:`) and an attachment made
 *  everywhere (null) are both answered on the platform. */
export function actionsKey(scope: string | null | undefined): string {
  return scope ?? PLATFORM;
}

async function actionsAt(api: IamAdminApi, scope: string): Promise<Record<string, boolean>> {
  try {
    const view = await api.access(scope === PLATFORM ? undefined : scope);
    return view?.actions ?? {};
  } catch {
    return {};
  }
}

const sorted = (scopes: (string | null | undefined)[]) => [...new Set(scopes.map(actionsKey))].sort();

/**
 * The names of the containers ``scopes`` are made of (container → name), as the caller may
 * list them (`GET /resources` at each): for ``ownerLabel`` and ``levelLabel``. Each container
 * is asked once; one the caller may not list stays unnamed (its id is shown).
 */
export function useContainerNames(api: IamAdminApi, scopes: (string | null | undefined)[]): Record<string, string> {
  const wanted = useMemo(() => sorted(scopes), [scopes]);
  const key = wanted.join('\n');
  const [names, setNames] = useState<Record<string, string>>({});
  const asked = useRef(new Set<string>());
  useEffect(() => {
    let cancelled = false;
    for (const { container, step } of containersOf(wanted)) {
      if (asked.current.has(container)) continue;
      asked.current.add(container);
      void nameOf(api, container, step).then((name) => {
        if (!cancelled && name) setNames((current) => ({ ...current, [container]: name }));
      });
    }
    return () => {
      cancelled = true;
    };
    // Asked again only for a container not asked yet.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, key]);
  return names;
}

/**
 * What the caller may do at each of ``scopes`` (`GET /access?scope=`, by ``actionsKey``), but
 * at ``here``, the page's own scope, whose answer is the page's ``can``. Unknown (not asked yet,
 * or refused) is an empty record: no button shows before IAM says it will answer.
 */
export function useActionsAt(
  api: IamAdminApi,
  scopes: (string | null | undefined)[],
  here: string,
  can: (action: string) => boolean,
): (scope: string | null | undefined) => Record<string, boolean> {
  const wanted = useMemo(() => sorted(scopes), [scopes]);
  const key = wanted.join('\n');
  const [found, setFound] = useState<Record<string, Record<string, boolean>>>({});
  const asked = useRef(new Set<string>());
  useEffect(() => {
    let cancelled = false;
    for (const scope of wanted) {
      if (scope === here || asked.current.has(scope)) continue;
      asked.current.add(scope);
      void actionsAt(api, scope).then((actions) => {
        if (!cancelled) setFound((current) => ({ ...current, [scope]: actions }));
      });
    }
    return () => {
      cancelled = true;
    };
    // Asked again only for a scope not asked yet.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, key, here]);
  return useCallback(
    (scope: string | null | undefined) => {
      const at = actionsKey(scope);
      if (at === here) {
        return new Proxy({}, { get: (_target, action: string) => can(action) }) as Record<string, boolean>;
      }
      return found[at] ?? {};
    },
    [found, here, can],
  );
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
  const owners = useMemo(() => sorted(scopes), [scopes]);
  const names = useContainerNames(api, owners);
  const at = useActionsAt(api, owners, here, can);

  return useMemo(() => {
    const found: Record<string, PolicyOwner> = {};
    for (const owner of owners) {
      const actions = at(owner);
      const any = owner === here || Object.values(actions).some(Boolean);
      found[owner] = {
        scope: owner,
        label: ownerLabel(owner, names),
        opens: owner !== here && any && ownerHref(owner) !== null,
        canUpdate: !!actions['iam:UpdatePolicy'],
        canDelete: !!actions['iam:DeletePolicy'],
      };
    }
    return found;
  }, [owners, here, at, names]);
}
