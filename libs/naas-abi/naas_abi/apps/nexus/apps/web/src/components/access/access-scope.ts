/**
 * The scope a Roles & permissions page manages: the platform, an organization or one of its
 * workspaces. It is the module's one parameter: every section asks the API about it, and the
 * caller's permissions there (`GET /api/iam/admin/access?scope=`) decide what is shown.
 *
 * IAM names a scope by its container, a path of `<service>:<type>/<id>` steps after `abi:`:
 * the organization `abi:nexus:organization/<org>`, its workspace
 * `abi:nexus:organization/<org>/nexus:workspace/<ws>`, a workspace in no organization
 * `abi:nexus:workspace/<ws>`. `<container>/*` is below it (the container and every container
 * under it) and `abi:` the platform.
 */

export type AccessLevel = 'platform' | 'organization' | 'workspace';

export type AccessScope = {
  level: AccessLevel;
  /** As the API names it: the organization's or the workspace's container, or null for the
   *  platform. */
  value: string | null;
  organizationId: string | null;
  workspaceId: string | null;
  label: string;
};

/** IAM's name of the platform, where a scope must be written (`grantable`, owners). */
export const PLATFORM = 'abi:';

/** An id as one segment of a name: percent-encoded UTF-8, every octet outside
 *  `A-Z a-z 0-9 - . _ ~` encoded (as IAM's `names.py`). */
export function encodeSegment(value: string): string {
  return encodeURIComponent(value).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

function decodeSegment(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** An organization's container: `abi:nexus:organization/<org>`. */
export function organizationContainer(organizationId: string): string {
  return `abi:nexus:organization/${encodeSegment(organizationId)}`;
}

/** A workspace's container: in its organization, or `abi:nexus:workspace/<ws>` in none. */
export function workspaceContainer(organizationId: string | null | undefined, workspaceId: string): string {
  const step = `nexus:workspace/${encodeSegment(workspaceId)}`;
  return organizationId ? `${organizationContainer(organizationId)}/${step}` : `abi:${step}`;
}

/** One step of a container's name: `<service>:<type>/<id>`, the id decoded. */
export type ContainerStep = { service: string; type: string; id: string };

/** A scope read back: the containers from the top (none for the platform), and whether it
 *  is below the last one (`<container>/*`). */
export type ParsedScope = { containers: ContainerStep[]; below: boolean };

const STEP = /^([a-z][a-z0-9_]*):([a-z][a-z0-9_]*)$/;

/** A scope as IAM writes it (`abi:`, `<container>` or `<container>/*`), or null for anything
 *  else (an unscoped attachment, a resource that is not a container). */
export function parseScope(scope: string | null | undefined): ParsedScope | null {
  if (!scope || !scope.startsWith('abi:')) return null;
  if (scope === PLATFORM) return { containers: [], below: false };
  let rest = scope.slice('abi:'.length);
  const below = rest.endsWith('/*');
  if (below) rest = rest.slice(0, -2);
  const tokens = rest.split('/');
  if (tokens.length % 2 !== 0) return null;
  const containers: ContainerStep[] = [];
  for (let i = 0; i < tokens.length; i += 2) {
    const head = STEP.exec(tokens[i]);
    const id = tokens[i + 1];
    if (!head || !id || id.includes(':') || id === '*') return null;
    containers.push({ service: head[1], type: head[2], id: decodeSegment(id) });
  }
  return { containers, below };
}

export const PLATFORM_ACCESS_SCOPE: AccessScope = {
  level: 'platform',
  value: null,
  organizationId: null,
  workspaceId: null,
  label: 'Platform',
};

export function organizationAccessScope(organizationId: string, label = 'Organization'): AccessScope {
  return {
    level: 'organization',
    value: organizationContainer(organizationId),
    organizationId,
    workspaceId: null,
    label,
  };
}

export function workspaceAccessScope(
  organizationId: string | null,
  workspaceId: string,
  label = 'Workspace',
): AccessScope {
  return {
    level: 'workspace',
    value: workspaceContainer(organizationId, workspaceId),
    organizationId,
    workspaceId,
    label,
  };
}

/** The scope written out, the platform as `abi:`: who owns what this page creates, and
 *  where the policy builder asks what the caller may grant. */
export function ownerOf(scope: AccessScope): string {
  return scope.value ?? PLATFORM;
}

/** Whether a policy or a group belongs to this page's level (one owned above is only
 *  attached here, never edited). A record without an owner is the platform's. */
export function ownedHere(scope: AccessScope, ownerScope: string | null | undefined): boolean {
  return (ownerScope ?? PLATFORM) === ownerOf(scope);
}
