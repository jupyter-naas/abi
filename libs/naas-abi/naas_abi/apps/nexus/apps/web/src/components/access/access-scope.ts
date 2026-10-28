/**
 * The scope a Roles & permissions page manages: the platform, an organization or one of its
 * workspaces. It is the module's one parameter: every section asks the API about it, and the
 * caller's permissions there (`GET /api/iam/admin/access?scope=`) decide what is shown.
 */

export type AccessLevel = 'platform' | 'organization' | 'workspace';

export type AccessScope = {
  level: AccessLevel;
  /** As the API names it: `abi:<org>:-`, `abi:<org>:<ws>`, or null for the platform. */
  value: string | null;
  organizationId: string | null;
  workspaceId: string | null;
  label: string;
};

/** IAM's name of the platform, where a scope must be written (`grantable`, owners). */
export const PLATFORM = 'abi:-:-';

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
    value: `abi:${organizationId}:-`,
    organizationId,
    workspaceId: null,
    label,
  };
}

export function workspaceAccessScope(organizationId: string, workspaceId: string, label = 'Workspace'): AccessScope {
  return {
    level: 'workspace',
    value: `abi:${organizationId}:${workspaceId}`,
    organizationId,
    workspaceId,
    label,
  };
}

/** The scope written out, the platform as `abi:-:-`: who owns what this page creates, and
 *  where the policy builder asks what the caller may grant. */
export function ownerOf(scope: AccessScope): string {
  return scope.value ?? PLATFORM;
}

/** Whether a policy or a group belongs to this page's level (one owned above is only
 *  attached here, never edited). A record without an owner is the platform's. */
export function ownedHere(scope: AccessScope, ownerScope: string | null | undefined): boolean {
  return (ownerScope ?? PLATFORM) === ownerOf(scope);
}
